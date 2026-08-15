use ab_codebase_index_a1::workload::materialize;

#[test]
fn copied_frozen_generator_matches_a0_four_document_golden() {
    let directory = tempfile::tempdir_in("/Data/CascadeProjects").unwrap();
    let workload = materialize(directory.path(), 4, 7).unwrap();
    assert_eq!(
        workload.manifest_sha256,
        "30131e41445986a6db0e635212ed0af6f5027e9c9bad8a826615042abd387eb8"
    );
    assert_eq!(
        (workload.symbols, workload.imports, workload.calls),
        (20, 9, 27)
    );
    assert_eq!(
        workload.symbols_sha256,
        "df0954e8a117833e694742b0aaf2fd57bef6475ce2d6d9d16c2a119eba7e782a"
    );
    assert_eq!(
        workload.imports_sha256,
        "e2ef88eb9f6064d670aa4a92948e665ad2eddda8cd97f5cb910c34699aa920de"
    );
    assert_eq!(
        workload.calls_sha256,
        "200368c3bb4c75c67734459559e7a9c5ec7426a1da65f45d6b741e9d349c8df0"
    );
    assert_eq!(
        workload.combined_sha256,
        "dece676cca475b92f9a9abcfe7bfd682557059cc9ac460bcd3380d1a64bb522e"
    );
}
