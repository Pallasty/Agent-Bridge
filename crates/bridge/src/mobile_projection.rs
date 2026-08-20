//! Ephemeral read-only projection protocol for a consent-visible mobile node.

use anyhow::{anyhow, bail, Context, Result};
use base64::{engine::general_purpose::STANDARD_NO_PAD, Engine};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::{HashMap, HashSet};
use std::io::{BufRead, BufReader, Read, Write};
use std::net::{IpAddr, SocketAddr, TcpListener, TcpStream};
use std::sync::Mutex;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

pub const PROJECTION_SCHEMA: &str = "agent_bridge.mobile_projection.frame.v1";
pub const MEDIA_CONTEXT_SCHEMA: &str = "agent_bridge.media_context.v0";
pub const MAX_SESSION_SECONDS: i64 = 600;
pub const MAX_ACTIONS: usize = 6;
const MAX_REQUEST_BYTES: usize = 6_000;
const MAX_FRAME_BYTES: usize = 16_384;
const MAX_TEXT_OBSERVATION_BYTES: usize = 4_096;
const CLOCK_SKEW_SECONDS: i64 = 30;
const MAX_PROJECTION_AUTH_NONCES: usize = 1_024;
const MAX_SERVED_FRAME_REVISIONS: usize = 256;
pub const TEXT_OBSERVATION_SCHEMA: &str = "agent_bridge.mobile_text_observation.v1";

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct MobileTextObservation {
    pub schema: String,
    pub session_id: String,
    pub captured_at_unix_seconds: i64,
    pub locale: String,
    pub submission_id: String,
    pub text: String,
    pub payload_sha256: String,
    pub retention_policy: String,
    pub foreground_user_submit: bool,
    pub attention_authority: bool,
    pub memory_authority: bool,
    pub actuation_authority: bool,
}

impl MobileTextObservation {
    fn validate(&self, session_id: &str, now: i64) -> Result<()> {
        if self.schema != TEXT_OBSERVATION_SCHEMA
            || self.session_id != session_id
            || self.retention_policy != "ephemeral_session_only"
            || !self.foreground_user_submit
            || self.attention_authority
            || self.memory_authority
            || self.actuation_authority
            || self.text.trim().is_empty()
            || self.text.chars().count() > 1_000
            || self.locale.is_empty()
            || self.locale.len() > 35
            || !is_lower_hex(&self.submission_id, 32)
            || (self.captured_at_unix_seconds - now).abs() > CLOCK_SKEW_SECONDS
        {
            bail!("invalid mobile text observation boundary");
        }
        let digest = hex(&Sha256::digest(self.text.as_bytes()));
        if !constant_time_eq(digest.as_bytes(), self.payload_sha256.as_bytes()) {
            bail!("mobile text observation digest mismatch");
        }
        Ok(())
    }
}

#[derive(Clone, Debug, PartialEq)]
pub enum ProjectionEvent {
    FrameServed {
        peer: SocketAddr,
        revision: u64,
        frame_sha256: String,
    },
    FrameRenderReported {
        peer: SocketAddr,
        revision: u64,
        frame_sha256: String,
        device_reported_at_unix_seconds: i64,
    },
    TextSubmitted {
        peer: SocketAddr,
        observation: MobileTextObservation,
    },
    TextSubmissionDeduplicated {
        peer: SocketAddr,
        submission_id: String,
        payload_sha256: String,
    },
}

#[derive(Default)]
struct TextSubmissionState {
    seen_nonces: HashSet<String>,
    accepted_submissions: HashMap<String, String>,
}

#[derive(Default)]
struct ProjectionProtocolState {
    abp1_seen_nonces: HashSet<String>,
    abr1_seen_nonces: HashSet<String>,
    served_frames: HashMap<u64, String>,
    highest_served_revision: Option<u64>,
}

impl ProjectionProtocolState {
    fn reserve_frame_pull(&mut self, nonce: &str, revision: u64, digest: &str) -> Result<()> {
        if revision == 0 {
            bail!("projection frame revision must be positive");
        }
        if self.abp1_seen_nonces.contains(nonce) {
            bail!("replayed projection frame nonce");
        }
        if self.abp1_seen_nonces.len() >= MAX_PROJECTION_AUTH_NONCES {
            bail!("projection frame nonce budget exhausted");
        }
        if self
            .highest_served_revision
            .is_some_and(|highest| revision < highest)
        {
            bail!("projection frame revision is not monotonic");
        }
        if let Some(existing_digest) = self.served_frames.get(&revision) {
            if !constant_time_eq(existing_digest.as_bytes(), digest.as_bytes()) {
                bail!("projection frame revision digest mismatch");
            }
        } else {
            if self.served_frames.len() >= MAX_SERVED_FRAME_REVISIONS {
                bail!("served projection frame budget exhausted");
            }
        }
        self.abp1_seen_nonces.insert(nonce.to_owned());
        Ok(())
    }

    fn record_frame_served(&mut self, revision: u64, digest: &str) {
        self.served_frames
            .entry(revision)
            .or_insert_with(|| digest.to_owned());
        self.highest_served_revision = Some(
            self.highest_served_revision
                .map_or(revision, |highest| highest.max(revision)),
        );
    }

    fn reserve_render_report(&mut self, nonce: &str, revision: u64, digest: &str) -> Result<()> {
        if revision == 0 {
            bail!("render report revision must be positive");
        }
        if self.abr1_seen_nonces.contains(nonce) {
            bail!("replayed projection render nonce");
        }
        if self.abr1_seen_nonces.len() >= MAX_PROJECTION_AUTH_NONCES {
            bail!("projection render nonce budget exhausted");
        }
        let served_digest = self
            .served_frames
            .get(&revision)
            .ok_or_else(|| anyhow!("render report references an unserved frame"))?;
        if !constant_time_eq(served_digest.as_bytes(), digest.as_bytes()) {
            bail!("render report frame digest mismatch");
        }
        self.abr1_seen_nonces.insert(nonce.to_owned());
        Ok(())
    }
}

/// Read-only media state that may be rendered by a mobile projection node.
/// It carries no controls or authority; clients should treat missing fields as
/// unknown rather than infering them from presentation text.
#[derive(Clone, Debug, Default, PartialEq, Serialize, Deserialize)]
pub struct MediaContext {
    pub schema: String,
    pub player: Option<String>,
    pub active_playlist_id: Option<String>,
    pub active_playlist_name: Option<String>,
    pub playback_status: Option<String>,
    pub track_id: Option<String>,
    pub artist: Option<String>,
    pub title: Option<String>,
    pub position_seconds: Option<f64>,
    pub duration_seconds: Option<f64>,
    pub metadata_available: bool,
    pub observed_at_unix_seconds: i64,
}

impl MediaContext {
    pub fn new(observed_at_unix_seconds: i64) -> Self {
        Self {
            schema: MEDIA_CONTEXT_SCHEMA.to_owned(),
            observed_at_unix_seconds,
            ..Self::default()
        }
    }

    pub fn changed_from(&self, previous: Option<&Self>) -> bool {
        previous != Some(self)
    }
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct ProjectionFrame {
    pub schema: String,
    pub session_id: String,
    pub revision: u64,
    pub expires_at_unix_seconds: i64,
    pub title: String,
    pub body: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub media_context: Option<MediaContext>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub status: Option<String>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub actions: Vec<String>,
    pub attention_authority: bool,
    pub memory_authority: bool,
    pub actuation_authority: bool,
}

impl ProjectionFrame {
    pub fn new(
        session_id: &str,
        revision: u64,
        expires_at: i64,
        title: &str,
        body: &str,
    ) -> Result<Self> {
        validate_session_id(session_id)?;
        if title.chars().count() > 160 || body.chars().count() > 8_000 {
            bail!("projection content exceeds bounded display limits");
        }
        Ok(Self {
            schema: PROJECTION_SCHEMA.to_owned(),
            session_id: session_id.to_owned(),
            revision,
            expires_at_unix_seconds: expires_at,
            title: title.to_owned(),
            body: body.to_owned(),
            media_context: None,
            status: None,
            actions: Vec::new(),
            attention_authority: false,
            memory_authority: false,
            actuation_authority: false,
        })
    }

    pub fn with_media_context(mut self, context: Option<MediaContext>) -> Result<Self> {
        if let Some(context) = &context {
            if context.schema != MEDIA_CONTEXT_SCHEMA {
                bail!("invalid media context schema");
            }
            for value in [
                &context.player,
                &context.active_playlist_id,
                &context.active_playlist_name,
                &context.playback_status,
                &context.track_id,
                &context.artist,
                &context.title,
            ] {
                if value
                    .as_ref()
                    .is_some_and(|text| text.chars().count() > 512)
                {
                    bail!("media context text exceeds bounded limits");
                }
            }
        }
        self.media_context = context;
        Ok(self)
    }

    pub fn with_presentation(mut self, status: Option<&str>, actions: &[String]) -> Result<Self> {
        if status.is_some_and(|value| value.chars().count() > 80)
            || actions.len() > MAX_ACTIONS
            || actions.iter().any(|value| value.chars().count() > 240)
        {
            bail!("projection presentation exceeds bounded display limits");
        }
        self.status = status.map(str::to_owned);
        self.actions = actions.to_vec();
        Ok(self)
    }
}

pub struct ProjectionSession {
    listener: TcpListener,
    token: [u8; 32],
    session_id: String,
    expires_at: i64,
    protocol_state: Mutex<ProjectionProtocolState>,
    text_submission_state: Mutex<TextSubmissionState>,
}

impl ProjectionSession {
    pub fn bind(
        address: IpAddr,
        port: u16,
        token_hex: &str,
        session_id: &str,
        expires_at: i64,
    ) -> Result<Self> {
        if !is_lan_address(address) {
            bail!("projection address must be a private or link-local LAN address");
        }
        validate_session_id(session_id)?;
        let now = unix_seconds()?;
        if expires_at <= now || expires_at - now > MAX_SESSION_SECONDS {
            bail!("projection session lifetime must be 1..={MAX_SESSION_SECONDS} seconds");
        }
        let listener =
            TcpListener::bind(SocketAddr::new(address, port)).context("bind projection session")?;
        Ok(Self {
            listener,
            token: decode_lower_hex_32(token_hex)?,
            session_id: session_id.to_owned(),
            expires_at,
            protocol_state: Mutex::new(ProjectionProtocolState::default()),
            text_submission_state: Mutex::new(TextSubmissionState::default()),
        })
    }

    pub fn local_addr(&self) -> Result<SocketAddr> {
        Ok(self.listener.local_addr()?)
    }

    /// Serve one authenticated protocol request. The caller owns the loop and can stop at
    /// any time; no worker thread or persistent service is created here.
    pub fn serve_next(
        &self,
        frame: &ProjectionFrame,
        timeout: Duration,
    ) -> Result<Option<ProjectionEvent>> {
        validate_frame(frame, &self.session_id, self.expires_at)?;
        self.listener.set_nonblocking(true)?;
        let deadline = Instant::now() + timeout;
        let (mut stream, peer) = loop {
            match self.listener.accept() {
                Ok(connection) => break connection,
                Err(error) if error.kind() == std::io::ErrorKind::WouldBlock => {
                    if Instant::now() >= deadline {
                        return Ok(None);
                    }
                    std::thread::sleep(Duration::from_millis(10));
                }
                Err(error) => return Err(error).context("accept projection client"),
            }
        };
        stream.set_read_timeout(Some(timeout))?;
        stream.set_write_timeout(Some(timeout))?;
        let event = serve_stream(
            &mut stream,
            &self.token,
            &self.session_id,
            self.expires_at,
            frame,
            &self.protocol_state,
            &self.text_submission_state,
        )?;
        Ok(Some(match event {
            ProjectionEvent::FrameServed {
                revision,
                frame_sha256,
                ..
            } => ProjectionEvent::FrameServed {
                peer,
                revision,
                frame_sha256,
            },
            ProjectionEvent::FrameRenderReported {
                revision,
                frame_sha256,
                device_reported_at_unix_seconds,
                ..
            } => ProjectionEvent::FrameRenderReported {
                peer,
                revision,
                frame_sha256,
                device_reported_at_unix_seconds,
            },
            ProjectionEvent::TextSubmitted { observation, .. } => {
                ProjectionEvent::TextSubmitted { peer, observation }
            }
            ProjectionEvent::TextSubmissionDeduplicated {
                submission_id,
                payload_sha256,
                ..
            } => ProjectionEvent::TextSubmissionDeduplicated {
                peer,
                submission_id,
                payload_sha256,
            },
        }))
    }
}

fn serve_stream(
    stream: &mut TcpStream,
    token: &[u8; 32],
    session_id: &str,
    expires_at: i64,
    frame: &ProjectionFrame,
    protocol_state: &Mutex<ProjectionProtocolState>,
    text_submission_state: &Mutex<TextSubmissionState>,
) -> Result<ProjectionEvent> {
    let mut request = Vec::new();
    BufReader::new(&mut *stream)
        .take((MAX_REQUEST_BYTES + 1) as u64)
        .read_until(b'\n', &mut request)?;
    if request.len() > MAX_REQUEST_BYTES {
        bail!("projection request too large");
    }
    while matches!(request.last(), Some(b'\n' | b'\r')) {
        request.pop();
    }
    let request = std::str::from_utf8(&request).context("projection request is not UTF-8")?;
    let fields: Vec<&str> = request.split(' ').collect();
    if fields.len() < 5 || fields[1] != session_id {
        bail!("invalid projection request");
    }
    let timestamp: i64 = fields[2].parse().context("invalid projection timestamp")?;
    let kind = fields[0];
    let valid_shape = match kind {
        "ABP1" => fields.len() == 5,
        "ABT1" => fields.len() == 6,
        "ABR1" => fields.len() == 7,
        _ => false,
    };
    let mac_field = match kind {
        "ABT1" => fields.get(5),
        "ABR1" => fields.get(6),
        _ => fields.get(4),
    };
    if !valid_shape
        || !is_lower_hex(fields[3], 32)
        || mac_field.is_none_or(|value| !is_lower_hex(value, 64))
    {
        bail!("invalid projection authentication fields");
    }
    let now = unix_seconds()?;
    if (timestamp - now).abs() > CLOCK_SKEW_SECONDS || now >= expires_at {
        bail!("expired projection request");
    }
    if kind == "ABR1" {
        let revision = fields[4]
            .parse::<u64>()
            .context("invalid projection render revision")?;
        if revision == 0 || revision.to_string() != fields[4] || !is_lower_hex(fields[5], 64) {
            bail!("invalid projection render authentication fields");
        }
    }
    let canonical = match kind {
        "ABT1" => format!(
            "ABT1\n{session_id}\n{timestamp}\n{}\n{}",
            fields[3], fields[4]
        ),
        "ABR1" => format!(
            "ABR1\n{session_id}\n{timestamp}\n{}\n{}\n{}",
            fields[3], fields[4], fields[5]
        ),
        _ => format!("ABP1\n{session_id}\n{timestamp}\n{}", fields[3]),
    };
    if !constant_time_eq(
        &hmac_sha256(token, canonical.as_bytes()),
        &decode_lower_hex_32(mac_field.unwrap())?,
    ) {
        bail!("invalid projection request MAC");
    }

    if kind == "ABT1" {
        let payload = STANDARD_NO_PAD
            .decode(fields[4])
            .context("invalid mobile text observation encoding")?;
        if payload.len() > MAX_TEXT_OBSERVATION_BYTES {
            bail!("mobile text observation too large");
        }
        let observation: MobileTextObservation =
            serde_json::from_slice(&payload).context("invalid mobile text observation payload")?;
        observation.validate(session_id, now)?;
        let digest = &observation.payload_sha256;
        let mut state = text_submission_state.lock().unwrap();
        let duplicate = match state.accepted_submissions.get(&observation.submission_id) {
            Some(accepted_digest)
                if constant_time_eq(accepted_digest.as_bytes(), digest.as_bytes()) =>
            {
                true
            }
            Some(_) => bail!("mobile text submission id payload mismatch"),
            None => false,
        };
        if !state.seen_nonces.insert(fields[3].to_owned()) && !duplicate {
            bail!("replayed mobile text observation nonce");
        }
        if !duplicate {
            state
                .accepted_submissions
                .insert(observation.submission_id.clone(), digest.clone());
        }
        let response_canonical =
            format!("ABT1R\n{session_id}\n{timestamp}\n{}\n{digest}", fields[3]);
        let mac = hex(&hmac_sha256(token, response_canonical.as_bytes()));
        writeln!(stream, "ACCEPTED {digest} {mac}")?;
        stream.flush()?;
        return Ok(if duplicate {
            ProjectionEvent::TextSubmissionDeduplicated {
                peer: stream.peer_addr()?,
                submission_id: observation.submission_id,
                payload_sha256: observation.payload_sha256,
            }
        } else {
            ProjectionEvent::TextSubmitted {
                peer: stream.peer_addr()?,
                observation,
            }
        });
    }

    if kind == "ABR1" {
        let revision: u64 = fields[4]
            .parse()
            .context("invalid render report revision")?;
        let digest = fields[5];
        let mut state = protocol_state
            .lock()
            .map_err(|_| anyhow!("projection protocol state unavailable"))?;
        state.reserve_render_report(fields[3], revision, digest)?;
        let response_canonical = format!(
            "ABR1R\n{session_id}\n{timestamp}\n{}\n{revision}\n{digest}",
            fields[3]
        );
        let mac = hex(&hmac_sha256(token, response_canonical.as_bytes()));
        writeln!(stream, "RENDERED {revision} {digest} {mac}")?;
        stream.flush()?;
        return Ok(ProjectionEvent::FrameRenderReported {
            peer: stream.peer_addr()?,
            revision,
            frame_sha256: digest.to_owned(),
            device_reported_at_unix_seconds: timestamp,
        });
    }

    let payload_bytes = serde_json::to_vec(frame)?;
    if payload_bytes.len() > MAX_FRAME_BYTES {
        bail!("projection frame too large");
    }
    let frame_sha256 = hex(&Sha256::digest(&payload_bytes));
    let payload = STANDARD_NO_PAD.encode(payload_bytes);
    let response_canonical = format!("ABP1R\n{session_id}\n{timestamp}\n{}\n{payload}", fields[3]);
    let mac = hex(&hmac_sha256(token, response_canonical.as_bytes()));
    let mut state = protocol_state
        .lock()
        .map_err(|_| anyhow!("projection protocol state unavailable"))?;
    state.reserve_frame_pull(fields[3], frame.revision, &frame_sha256)?;
    writeln!(stream, "OK {payload} {mac}")?;
    stream.flush()?;
    state.record_frame_served(frame.revision, &frame_sha256);
    Ok(ProjectionEvent::FrameServed {
        peer: stream.peer_addr()?,
        revision: frame.revision,
        frame_sha256,
    })
}

/// SHA-256 of the exact UTF-8 JSON payload bytes transported by ABP1.
pub fn projection_frame_sha256(frame: &ProjectionFrame) -> Result<String> {
    let payload = serde_json::to_vec(frame).context("serialize projection frame")?;
    Ok(hex(&Sha256::digest(payload)))
}

fn validate_frame(frame: &ProjectionFrame, session_id: &str, expires_at: i64) -> Result<()> {
    if frame.schema != PROJECTION_SCHEMA
        || frame.session_id != session_id
        || frame.expires_at_unix_seconds != expires_at
    {
        bail!("projection frame does not match session");
    }
    if frame.revision == 0 {
        bail!("projection frame revision must be positive");
    }
    if frame.attention_authority || frame.memory_authority || frame.actuation_authority {
        bail!("projection frame asserts forbidden authority");
    }
    Ok(())
}

fn validate_session_id(value: &str) -> Result<()> {
    if value.is_empty()
        || value.len() > 64
        || !value
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || b"_.-".contains(&b))
    {
        bail!("invalid projection session id");
    }
    Ok(())
}

fn is_lan_address(address: IpAddr) -> bool {
    match address {
        IpAddr::V4(address) => address.is_private() || address.is_link_local(),
        IpAddr::V6(address) => {
            address.is_unicast_link_local() || (address.segments()[0] & 0xfe00) == 0xfc00
        }
    }
}

fn unix_seconds() -> Result<i64> {
    Ok(SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|_| anyhow!("system clock before Unix epoch"))?
        .as_secs() as i64)
}

fn decode_lower_hex_32(value: &str) -> Result<[u8; 32]> {
    if !is_lower_hex(value, 64) {
        bail!("expected 64 lowercase hex characters");
    }
    let mut out = [0u8; 32];
    for (i, byte) in out.iter_mut().enumerate() {
        *byte = u8::from_str_radix(&value[i * 2..i * 2 + 2], 16)?;
    }
    Ok(out)
}
fn is_lower_hex(value: &str, len: usize) -> bool {
    value.len() == len
        && value
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}
fn hmac_sha256(key: &[u8], message: &[u8]) -> [u8; 32] {
    let mut key_block = [0u8; 64];
    if key.len() > 64 {
        key_block[..32].copy_from_slice(&Sha256::digest(key));
    } else {
        key_block[..key.len()].copy_from_slice(key);
    }
    let mut inner = [0x36u8; 64];
    let mut outer = [0x5cu8; 64];
    for i in 0..64 {
        inner[i] ^= key_block[i];
        outer[i] ^= key_block[i];
    }
    let inner_hash = Sha256::new()
        .chain_update(inner)
        .chain_update(message)
        .finalize();
    Sha256::new()
        .chain_update(outer)
        .chain_update(inner_hash)
        .finalize()
        .into()
}
fn constant_time_eq(left: &[u8], right: &[u8]) -> bool {
    left.len() == right.len() && left.iter().zip(right).fold(0u8, |d, (a, b)| d | (a ^ b)) == 0
}
fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::thread;

    fn exchange_request(
        request: String,
        token: &[u8; 32],
        session_id: &str,
        expires_at: i64,
        frame: &ProjectionFrame,
        protocol_state: &Mutex<ProjectionProtocolState>,
        text_submission_state: &Mutex<TextSubmissionState>,
    ) -> (Result<ProjectionEvent>, String) {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let address = listener.local_addr().unwrap();
        let client = thread::spawn(move || {
            let mut stream = TcpStream::connect(address).unwrap();
            stream.write_all(request.as_bytes()).unwrap();
            let mut response = String::new();
            BufReader::new(stream).read_line(&mut response).unwrap();
            response
        });
        let (mut stream, _) = listener.accept().unwrap();
        let event = serve_stream(
            &mut stream,
            token,
            session_id,
            expires_at,
            frame,
            protocol_state,
            text_submission_state,
        );
        drop(stream);
        (event, client.join().unwrap())
    }

    fn pull_request(token: &[u8; 32], session_id: &str, timestamp: i64, nonce: &str) -> String {
        let canonical = format!("ABP1\n{session_id}\n{timestamp}\n{nonce}");
        let mac = hex(&hmac_sha256(token, canonical.as_bytes()));
        format!("ABP1 {session_id} {timestamp} {nonce} {mac}\n")
    }

    fn render_request(
        token: &[u8; 32],
        session_id: &str,
        timestamp: i64,
        nonce: &str,
        revision: u64,
        digest: &str,
    ) -> String {
        let canonical = format!("ABR1\n{session_id}\n{timestamp}\n{nonce}\n{revision}\n{digest}");
        let mac = hex(&hmac_sha256(token, canonical.as_bytes()));
        format!("ABR1 {session_id} {timestamp} {nonce} {revision} {digest} {mac}\n")
    }

    #[test]
    fn frame_is_always_zero_authority() {
        let frame = ProjectionFrame::new("session-1", 1, 1234, "Status", "Ready").unwrap();
        assert!(
            !frame.attention_authority && !frame.memory_authority && !frame.actuation_authority
        );
        assert!(ProjectionFrame::new("bad session", 1, 1234, "", "").is_err());
        assert!(ProjectionFrame::new("ok", 1, 1234, "", &"x".repeat(8001)).is_err());
    }

    #[test]
    fn frame_revision_can_advance_without_changing_session_boundary() {
        let first = ProjectionFrame::new("session-1", 1, 1234, "Status", "Ready").unwrap();
        let second = ProjectionFrame::new("session-1", 2, 1234, "Status", "Updated").unwrap();
        assert_eq!(second.revision, first.revision + 1);
        assert_eq!(second.session_id, first.session_id);
        assert_eq!(
            second.expires_at_unix_seconds,
            first.expires_at_unix_seconds
        );
        assert!(!second.attention_authority);
        assert!(!second.memory_authority);
        assert!(!second.actuation_authority);
    }

    #[test]
    fn structured_presentation_is_optional_and_bounded() {
        let actions = vec![
            "Review the result".to_string(),
            "Disconnect when done".to_string(),
        ];
        let frame = ProjectionFrame::new("session-1", 1, 1234, "Status", "Ready")
            .unwrap()
            .with_presentation(Some("Needs review"), &actions)
            .unwrap();
        assert_eq!(frame.status.as_deref(), Some("Needs review"));
        assert_eq!(frame.actions, actions);
        assert!(ProjectionFrame::new("session-1", 1, 1234, "", "")
            .unwrap()
            .with_presentation(None, &vec!["x".into(); MAX_ACTIONS + 1])
            .is_err());
    }

    #[test]
    fn media_context_is_bounded_read_only_and_change_detectable() {
        let mut context = MediaContext::new(1234);
        context.player = Some("rhythmbox".into());
        context.title = Some("Ready For Love".into());
        context.metadata_available = true;
        let frame = ProjectionFrame::new("session-1", 1, 1234, "Media", "Now playing")
            .unwrap()
            .with_media_context(Some(context.clone()))
            .unwrap();
        assert_eq!(frame.media_context.as_ref(), Some(&context));
        assert!(!context.changed_from(Some(&context)));
        let mut changed = context.clone();
        changed.title = Some("Next track".into());
        assert!(changed.changed_from(Some(&context)));
        assert!(
            ProjectionFrame::new("session-1", 1, 1234, "Media", "Now playing")
                .unwrap()
                .with_media_context(Some(MediaContext {
                    schema: "wrong".into(),
                    ..context
                }))
                .is_err()
        );
    }

    #[test]
    fn projection_hmac_known_answer() {
        assert_eq!(
            hex(&hmac_sha256(&[0x0b; 20], b"Hi There")),
            "b0344c61d8db38535ca8afceaf0bf12b881dc200c9833da726e9376c2e32cff7"
        );
    }

    #[test]
    fn projection_frame_digest_and_render_hmac_known_answers() {
        let frame = ProjectionFrame::new("projection-1", 7, 1234, "AB", "Ready").unwrap();
        let digest = projection_frame_sha256(&frame).unwrap();
        assert_eq!(
            digest,
            "4ebdb4f6e4332d8d8ec1c9417045a6c4791aa668fbede4ecd53e8f08eb1b1699"
        );
        let canonical = format!(
            "ABR1\nprojection-1\n1700000000\n0123456789abcdef0123456789abcdef\n7\n{digest}"
        );
        assert_eq!(
            hex(&hmac_sha256(&[0x11; 32], canonical.as_bytes())),
            "18d817b6f2385a008c6e751f8f897b2c90d21069715b18722e89049f686afcdf"
        );
        let response_canonical = format!(
            "ABR1R\nprojection-1\n1700000000\n0123456789abcdef0123456789abcdef\n7\n{digest}"
        );
        assert_eq!(
            hex(&hmac_sha256(&[0x11; 32], response_canonical.as_bytes())),
            "7e945a8433cf852731e3402998d08a257c08893e2b6133907313dd948e4529b4"
        );

        // Cross-language drift gate shared verbatim with Android ProtocolTest.
        let android_digest = "9cca83a4561232783196fc8a3f5361ef7bd1d41fdfe04700e49b662dae527adb";
        let android_request_canonical = format!(
            "ABR1\nprojection-1\n1700000000\n0123456789abcdef0123456789abcdef\n7\n{android_digest}"
        );
        assert_eq!(
            hex(&hmac_sha256(
                &[0x11; 32],
                android_request_canonical.as_bytes()
            )),
            "b81cd8e26188dfeaff025cb2d840e657d2308eeaf234f5a693394922c93e9545"
        );
        let android_response_canonical = format!(
            "ABR1R\nprojection-1\n1700000000\n0123456789abcdef0123456789abcdef\n7\n{android_digest}"
        );
        assert_eq!(
            hex(&hmac_sha256(
                &[0x11; 32],
                android_response_canonical.as_bytes()
            )),
            "3d49253c3b4ca929eaafc2b567ba065081ae87917a0f431fd136f6a89b57b8c6"
        );
    }

    #[test]
    fn authenticated_pull_returns_bound_frame() {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let address = listener.local_addr().unwrap();
        let token = [0x11u8; 32];
        let token_for_server = token;
        let session = "projection-1";
        let expires = unix_seconds().unwrap() + 60;
        let frame = ProjectionFrame::new(session, 3, expires, "AB", "Ready").unwrap();
        let frame_for_server = frame.clone();
        let expected_digest = projection_frame_sha256(&frame).unwrap();
        let expected_digest_for_server = expected_digest.clone();
        let server = thread::spawn(move || {
            let (mut stream, _) = listener.accept().unwrap();
            let event = serve_stream(
                &mut stream,
                &token_for_server,
                session,
                expires,
                &frame_for_server,
                &Mutex::new(ProjectionProtocolState::default()),
                &Mutex::new(TextSubmissionState::default()),
            )
            .unwrap();
            assert_eq!(
                event,
                ProjectionEvent::FrameServed {
                    peer: stream.peer_addr().unwrap(),
                    revision: 3,
                    frame_sha256: expected_digest_for_server,
                }
            );
        });
        let timestamp = unix_seconds().unwrap();
        let nonce = "0123456789abcdef0123456789abcdef";
        let canonical = format!("ABP1\n{session}\n{timestamp}\n{nonce}");
        let request_mac = hex(&hmac_sha256(&token, canonical.as_bytes()));
        let mut stream = TcpStream::connect(address).unwrap();
        writeln!(stream, "ABP1 {session} {timestamp} {nonce} {request_mac}").unwrap();
        let mut response = String::new();
        BufReader::new(stream).read_line(&mut response).unwrap();
        server.join().unwrap();
        let fields: Vec<&str> = response.trim().split(' ').collect();
        assert_eq!(fields.len(), 3);
        let response_canonical = format!("ABP1R\n{session}\n{timestamp}\n{nonce}\n{}", fields[1]);
        assert_eq!(
            fields[2],
            hex(&hmac_sha256(&token, response_canonical.as_bytes()))
        );
        let decoded: ProjectionFrame =
            serde_json::from_slice(&STANDARD_NO_PAD.decode(fields[1]).unwrap()).unwrap();
        assert_eq!(decoded, frame);
        assert_eq!(
            hex(&Sha256::digest(STANDARD_NO_PAD.decode(fields[1]).unwrap())),
            expected_digest
        );
    }

    #[test]
    fn render_report_requires_exact_served_pair_and_is_replay_safe() {
        let token = [0x11u8; 32];
        let session_id = "projection-1";
        let timestamp = unix_seconds().unwrap();
        let expires = timestamp + 60;
        let frame = ProjectionFrame::new(session_id, 7, expires, "AB", "Ready").unwrap();
        let digest = projection_frame_sha256(&frame).unwrap();
        let protocol_state = Mutex::new(ProjectionProtocolState::default());
        let text_state = Mutex::new(TextSubmissionState::default());

        let pull_nonce = "0123456789abcdef0123456789abcdef";
        let (pull_event, pull_response) = exchange_request(
            pull_request(&token, session_id, timestamp, pull_nonce),
            &token,
            session_id,
            expires,
            &frame,
            &protocol_state,
            &text_state,
        );
        assert!(pull_response.starts_with("OK "));
        assert!(matches!(
            pull_event.unwrap(),
            ProjectionEvent::FrameServed {
                revision: 7,
                frame_sha256,
                ..
            } if frame_sha256 == digest
        ));

        let render_nonce = "11111111111111111111111111111111";
        let request = render_request(
            &token,
            session_id,
            timestamp,
            render_nonce,
            frame.revision,
            &digest,
        );
        let (event, response) = exchange_request(
            request.clone(),
            &token,
            session_id,
            expires,
            &frame,
            &protocol_state,
            &text_state,
        );
        match event.unwrap() {
            ProjectionEvent::FrameRenderReported {
                revision,
                frame_sha256,
                device_reported_at_unix_seconds,
                ..
            } => {
                assert_eq!(revision, frame.revision);
                assert_eq!(frame_sha256, digest);
                assert_eq!(device_reported_at_unix_seconds, timestamp);
            }
            other => panic!("unexpected projection event: {other:?}"),
        }
        let fields: Vec<&str> = response.trim().split(' ').collect();
        assert_eq!(fields[..3], ["RENDERED", "7", digest.as_str()]);
        let response_canonical =
            format!("ABR1R\n{session_id}\n{timestamp}\n{render_nonce}\n7\n{digest}");
        assert_eq!(
            fields[3],
            hex(&hmac_sha256(&token, response_canonical.as_bytes()))
        );

        // A device that loses the authenticated response may report the same exact
        // served pair again, but it must use a fresh nonce.
        let retry_nonce = "77777777777777777777777777777777";
        let (response_loss_retry, retry_response) = exchange_request(
            render_request(
                &token,
                session_id,
                timestamp,
                retry_nonce,
                frame.revision,
                &digest,
            ),
            &token,
            session_id,
            expires,
            &frame,
            &protocol_state,
            &text_state,
        );
        assert!(matches!(
            response_loss_retry.unwrap(),
            ProjectionEvent::FrameRenderReported {
                revision: 7,
                frame_sha256,
                ..
            } if frame_sha256 == digest
        ));
        assert!(retry_response.starts_with(&format!("RENDERED 7 {digest} ")));

        let (replay, _) = exchange_request(
            request,
            &token,
            session_id,
            expires,
            &frame,
            &protocol_state,
            &text_state,
        );
        assert!(replay.unwrap_err().to_string().contains("replayed"));

        let wrong_digest = "00".repeat(32);
        let (mismatch, _) = exchange_request(
            render_request(
                &token,
                session_id,
                timestamp,
                "22222222222222222222222222222222",
                frame.revision,
                &wrong_digest,
            ),
            &token,
            session_id,
            expires,
            &frame,
            &protocol_state,
            &text_state,
        );
        assert!(mismatch
            .unwrap_err()
            .to_string()
            .contains("digest mismatch"));

        let (unsent, _) = exchange_request(
            render_request(
                &token,
                session_id,
                timestamp,
                "33333333333333333333333333333333",
                frame.revision + 1,
                &digest,
            ),
            &token,
            session_id,
            expires,
            &frame,
            &protocol_state,
            &text_state,
        );
        assert!(unsent.unwrap_err().to_string().contains("unserved"));

        // Serving revision 7 cannot be used as evidence that any lower revision
        // was served; render reports require exact membership, never >= inference.
        let (unsent_lower_revision, _) = exchange_request(
            render_request(
                &token,
                session_id,
                timestamp,
                "88888888888888888888888888888888",
                frame.revision - 1,
                &digest,
            ),
            &token,
            session_id,
            expires,
            &frame,
            &protocol_state,
            &text_state,
        );
        assert!(unsent_lower_revision
            .unwrap_err()
            .to_string()
            .contains("unserved"));

        let zero_revision = render_request(
            &token,
            session_id,
            timestamp,
            "44444444444444444444444444444444",
            0,
            &digest,
        );
        let (zero, _) = exchange_request(
            zero_revision,
            &token,
            session_id,
            expires,
            &frame,
            &protocol_state,
            &text_state,
        );
        assert!(zero.is_err());

        let noncanonical_nonce = "99999999999999999999999999999999";
        let noncanonical_revision = "07";
        let noncanonical_canonical = format!(
            "ABR1\n{session_id}\n{timestamp}\n{noncanonical_nonce}\n{noncanonical_revision}\n{digest}"
        );
        let noncanonical_mac = hex(&hmac_sha256(&token, noncanonical_canonical.as_bytes()));
        let noncanonical_request = format!(
            "ABR1 {session_id} {timestamp} {noncanonical_nonce} {noncanonical_revision} {digest} {noncanonical_mac}\n"
        );
        let (noncanonical, _) = exchange_request(
            noncanonical_request,
            &token,
            session_id,
            expires,
            &frame,
            &protocol_state,
            &text_state,
        );
        assert!(noncanonical.is_err());

        let mut bad_mac = render_request(
            &token,
            session_id,
            timestamp,
            "55555555555555555555555555555555",
            frame.revision,
            &digest,
        );
        let mac_start = bad_mac.trim_end().rfind(' ').unwrap() + 1;
        bad_mac.replace_range(mac_start..mac_start + 64, &"00".repeat(32));
        let (bad_mac_result, _) = exchange_request(
            bad_mac,
            &token,
            session_id,
            expires,
            &frame,
            &protocol_state,
            &text_state,
        );
        assert!(bad_mac_result
            .unwrap_err()
            .to_string()
            .contains("request MAC"));

        let wrong_session_request = render_request(
            &token,
            "projection-2",
            timestamp,
            "66666666666666666666666666666666",
            frame.revision,
            &digest,
        );
        let (wrong_session, _) = exchange_request(
            wrong_session_request,
            &token,
            session_id,
            expires,
            &frame,
            &protocol_state,
            &text_state,
        );
        assert!(wrong_session.is_err());
    }

    #[test]
    fn projection_protocol_state_is_monotonic_bounded_and_fail_closed() {
        let digest = "11".repeat(32);
        let mut state = ProjectionProtocolState::default();
        state
            .reserve_frame_pull("00000000000000000000000000000000", 2, &digest)
            .unwrap();
        state.record_frame_served(2, &digest);
        assert!(state
            .reserve_frame_pull("00000000000000000000000000000000", 2, &digest)
            .unwrap_err()
            .to_string()
            .contains("replayed"));
        assert!(state
            .reserve_frame_pull("00000000000000000000000000000001", 2, &"22".repeat(32))
            .unwrap_err()
            .to_string()
            .contains("digest mismatch"));
        assert!(state
            .reserve_frame_pull("00000000000000000000000000000002", 1, &digest)
            .unwrap_err()
            .to_string()
            .contains("not monotonic"));

        let mut nonce_full = ProjectionProtocolState::default();
        nonce_full.abp1_seen_nonces = (0..MAX_PROJECTION_AUTH_NONCES)
            .map(|value| format!("{value:032x}"))
            .collect();
        assert!(nonce_full
            .reserve_frame_pull("ffffffffffffffffffffffffffffffff", 1, &digest)
            .unwrap_err()
            .to_string()
            .contains("budget exhausted"));

        let mut frames_full = ProjectionProtocolState::default();
        for revision in 1..=MAX_SERVED_FRAME_REVISIONS as u64 {
            frames_full.served_frames.insert(revision, digest.clone());
        }
        frames_full.highest_served_revision = Some(MAX_SERVED_FRAME_REVISIONS as u64);
        assert!(frames_full
            .reserve_frame_pull(
                "ffffffffffffffffffffffffffffffff",
                MAX_SERVED_FRAME_REVISIONS as u64 + 1,
                &digest,
            )
            .unwrap_err()
            .to_string()
            .contains("budget exhausted"));

        let mut render_nonce_full = ProjectionProtocolState::default();
        render_nonce_full.served_frames.insert(1, digest.clone());
        render_nonce_full.abr1_seen_nonces = (0..MAX_PROJECTION_AUTH_NONCES)
            .map(|value| format!("{value:032x}"))
            .collect();
        assert!(render_nonce_full
            .reserve_render_report("ffffffffffffffffffffffffffffffff", 1, &digest)
            .unwrap_err()
            .to_string()
            .contains("budget exhausted"));
    }

    #[test]
    fn authenticated_text_submission_is_ephemeral_zero_authority_and_replay_safe() {
        let token = [0x11u8; 32];
        let session_id = "projection-1";
        let timestamp = unix_seconds().unwrap();
        let nonce = "0123456789abcdef0123456789abcdef";
        let text = "hello from phone";
        let digest = hex(&Sha256::digest(text.as_bytes()));
        let observation = MobileTextObservation {
            schema: TEXT_OBSERVATION_SCHEMA.into(),
            session_id: session_id.into(),
            captured_at_unix_seconds: timestamp,
            locale: "en-US".into(),
            submission_id: "abcdef0123456789abcdef0123456789".into(),
            text: text.into(),
            payload_sha256: digest.clone(),
            retention_policy: "ephemeral_session_only".into(),
            foreground_user_submit: true,
            attention_authority: false,
            memory_authority: false,
            actuation_authority: false,
        };
        let mut invalid_digest = observation.clone();
        invalid_digest.payload_sha256 = "00".repeat(32);
        assert!(invalid_digest.validate(session_id, timestamp).is_err());
        let mut invalid_authority = observation.clone();
        invalid_authority.memory_authority = true;
        assert!(invalid_authority.validate(session_id, timestamp).is_err());
        let payload = STANDARD_NO_PAD.encode(serde_json::to_vec(&observation).unwrap());
        let canonical = format!("ABT1\n{session_id}\n{timestamp}\n{nonce}\n{payload}");
        let mac = hex(&hmac_sha256(&token, canonical.as_bytes()));
        let request = format!("ABT1 {session_id} {timestamp} {nonce} {payload} {mac}\n");
        let first_request = request.clone();
        let frame = ProjectionFrame::new(session_id, 1, timestamp + 60, "AB", "Ready").unwrap();
        let protocol_state = Mutex::new(ProjectionProtocolState::default());
        let seen = Mutex::new(TextSubmissionState::default());

        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let address = listener.local_addr().unwrap();
        let client = thread::spawn(move || {
            let mut stream = TcpStream::connect(address).unwrap();
            stream.write_all(first_request.as_bytes()).unwrap();
            let mut response = String::new();
            BufReader::new(stream).read_line(&mut response).unwrap();
            response
        });
        let (mut stream, _) = listener.accept().unwrap();
        let event = serve_stream(
            &mut stream,
            &token,
            session_id,
            timestamp + 60,
            &frame,
            &protocol_state,
            &seen,
        )
        .unwrap();
        let response = client.join().unwrap();
        assert!(response.starts_with(&format!("ACCEPTED {digest} ")));
        assert_eq!(
            event,
            ProjectionEvent::TextSubmitted {
                peer: stream.peer_addr().unwrap(),
                observation
            }
        );
        assert_eq!(seen.lock().unwrap().seen_nonces.len(), 1);
        assert_eq!(seen.lock().unwrap().accepted_submissions.len(), 1);

        let replay_nonce = "fedcba9876543210fedcba9876543210";
        let replay_canonical =
            format!("ABT1\n{session_id}\n{timestamp}\n{replay_nonce}\n{payload}");
        let replay_mac = hex(&hmac_sha256(&token, replay_canonical.as_bytes()));
        let replay_request =
            format!("ABT1 {session_id} {timestamp} {replay_nonce} {payload} {replay_mac}\n");
        let replay_listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let replay_address = replay_listener.local_addr().unwrap();
        let replay_client = thread::spawn(move || {
            let mut stream = TcpStream::connect(replay_address).unwrap();
            stream.write_all(replay_request.as_bytes()).unwrap();
            let mut response = String::new();
            BufReader::new(stream).read_line(&mut response).unwrap();
            response
        });
        let (mut replay_stream, _) = replay_listener.accept().unwrap();
        let replay_event = serve_stream(
            &mut replay_stream,
            &token,
            session_id,
            timestamp + 60,
            &frame,
            &protocol_state,
            &seen,
        )
        .unwrap();
        let replay_response = replay_client.join().unwrap();
        assert!(replay_response.starts_with(&format!("ACCEPTED {digest} ")));
        assert_eq!(
            replay_event,
            ProjectionEvent::TextSubmissionDeduplicated {
                peer: replay_stream.peer_addr().unwrap(),
                submission_id: "abcdef0123456789abcdef0123456789".into(),
                payload_sha256: digest,
            }
        );
        assert_eq!(seen.lock().unwrap().seen_nonces.len(), 2);
        assert_eq!(seen.lock().unwrap().accepted_submissions.len(), 1);
    }
}
