//! Ephemeral read-only projection protocol for a consent-visible mobile node.

use anyhow::{anyhow, bail, Context, Result};
use base64::{engine::general_purpose::STANDARD_NO_PAD, Engine};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::io::{BufRead, BufReader, Read, Write};
use std::net::{IpAddr, SocketAddr, TcpListener, TcpStream};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

pub const PROJECTION_SCHEMA: &str = "agent_bridge.mobile_projection.frame.v1";
pub const MAX_SESSION_SECONDS: i64 = 600;
pub const MAX_ACTIONS: usize = 6;
const MAX_REQUEST_BYTES: usize = 512;
const MAX_FRAME_BYTES: usize = 16_384;
const CLOCK_SKEW_SECONDS: i64 = 30;

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct ProjectionFrame {
    pub schema: String,
    pub session_id: String,
    pub revision: u64,
    pub expires_at_unix_seconds: i64,
    pub title: String,
    pub body: String,
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
            status: None,
            actions: Vec::new(),
            attention_authority: false,
            memory_authority: false,
            actuation_authority: false,
        })
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
        })
    }

    pub fn local_addr(&self) -> Result<SocketAddr> {
        Ok(self.listener.local_addr()?)
    }

    /// Serve one authenticated pull. The caller owns the loop and can stop at
    /// any time; no worker thread or persistent service is created here.
    pub fn serve_next(
        &self,
        frame: &ProjectionFrame,
        timeout: Duration,
    ) -> Result<Option<SocketAddr>> {
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
        serve_stream(
            &mut stream,
            &self.token,
            &self.session_id,
            self.expires_at,
            frame,
        )?;
        Ok(Some(peer))
    }
}

fn serve_stream(
    stream: &mut TcpStream,
    token: &[u8; 32],
    session_id: &str,
    expires_at: i64,
    frame: &ProjectionFrame,
) -> Result<()> {
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
    if fields.len() != 5 || fields[0] != "ABP1" || fields[1] != session_id {
        bail!("invalid projection request");
    }
    let timestamp: i64 = fields[2].parse().context("invalid projection timestamp")?;
    if !is_lower_hex(fields[3], 32) || !is_lower_hex(fields[4], 64) {
        bail!("invalid projection authentication fields");
    }
    let now = unix_seconds()?;
    if (timestamp - now).abs() > CLOCK_SKEW_SECONDS || now >= expires_at {
        bail!("expired projection request");
    }
    let canonical = format!("ABP1\n{session_id}\n{timestamp}\n{}", fields[3]);
    if !constant_time_eq(
        &hmac_sha256(token, canonical.as_bytes()),
        &decode_lower_hex_32(fields[4])?,
    ) {
        bail!("invalid projection request MAC");
    }

    let payload = serde_json::to_vec(frame)?;
    if payload.len() > MAX_FRAME_BYTES {
        bail!("projection frame too large");
    }
    let payload = STANDARD_NO_PAD.encode(payload);
    let response_canonical = format!("ABP1R\n{session_id}\n{timestamp}\n{}\n{payload}", fields[3]);
    let mac = hex(&hmac_sha256(token, response_canonical.as_bytes()));
    writeln!(stream, "OK {payload} {mac}")?;
    stream.flush()?;
    Ok(())
}

fn validate_frame(frame: &ProjectionFrame, session_id: &str, expires_at: i64) -> Result<()> {
    if frame.schema != PROJECTION_SCHEMA
        || frame.session_id != session_id
        || frame.expires_at_unix_seconds != expires_at
    {
        bail!("projection frame does not match session");
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
    fn projection_hmac_known_answer() {
        assert_eq!(
            hex(&hmac_sha256(&[0x0b; 20], b"Hi There")),
            "b0344c61d8db38535ca8afceaf0bf12b881dc200c9833da726e9376c2e32cff7"
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
        let server = thread::spawn(move || {
            let (mut stream, _) = listener.accept().unwrap();
            serve_stream(
                &mut stream,
                &token_for_server,
                session,
                expires,
                &frame_for_server,
            )
            .unwrap();
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
    }
}
