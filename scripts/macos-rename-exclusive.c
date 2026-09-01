#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

#ifndef RENAME_EXCL
#define RENAME_EXCL 0x00000004
#endif

int main(int argc, char **argv) {
    if (argc != 3 || argv[1][0] != '/' || argv[2][0] != '/') {
        fprintf(stderr, "usage: macos-rename-exclusive ABS_SOURCE ABS_DESTINATION\n");
        return 64;
    }
#if defined(__APPLE__)
    if (renameatx_np(AT_FDCWD, argv[1], AT_FDCWD, argv[2], RENAME_EXCL) != 0) {
        int error = errno;
        fprintf(stderr, "renameatx_np(RENAME_EXCL): %s\n", strerror(error));
        return error == EEXIST ? 73 : 74;
    }
    return 0;
#else
    (void)argv;
    fprintf(stderr, "macos-rename-exclusive requires Darwin\n");
    return 69;
#endif
}
