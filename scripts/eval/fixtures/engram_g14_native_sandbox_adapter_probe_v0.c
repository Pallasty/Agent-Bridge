#define _DARWIN_C_SOURCE 1
#define _GNU_SOURCE 1

#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>

#if defined(__APPLE__)
#include <sys/syscall.h>
#elif defined(__linux__)
#include <linux/audit.h>
#include <linux/filter.h>
#include <linux/seccomp.h>
#include <stddef.h>
#include <sys/prctl.h>
#include <sys/syscall.h>
#endif

enum {
    CLOCK_LIBC_CLOCK_GETTIME = 1u << 0,
    CLOCK_LIBC_GETTIMEOFDAY = 1u << 1,
    CLOCK_LIBC_TIME = 1u << 2,
    CLOCK_DIRECT_SYSCALL = 1u << 3,
};

static uint32_t clock_observation_mask(void) {
    uint32_t mask = 0;
    struct timespec timespec_value = {0};
    struct timeval timeval_value = {0};
    time_t time_value = 0;

    errno = 0;
    if (clock_gettime(CLOCK_REALTIME, &timespec_value) == 0) {
        mask |= CLOCK_LIBC_CLOCK_GETTIME;
    }
    errno = 0;
    if (gettimeofday(&timeval_value, NULL) == 0) {
        mask |= CLOCK_LIBC_GETTIMEOFDAY;
    }
    errno = 0;
    if (time(&time_value) != (time_t)-1) {
        mask |= CLOCK_LIBC_TIME;
    }

#if defined(__APPLE__) && defined(SYS_gettimeofday)
    errno = 0;
#if defined(__clang__)
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wdeprecated-declarations"
#endif
    if (syscall(SYS_gettimeofday, &timeval_value, NULL) == 0) {
        mask |= CLOCK_DIRECT_SYSCALL;
    }
#if defined(__clang__)
#pragma clang diagnostic pop
#endif
#elif defined(__linux__) && defined(__NR_clock_gettime)
    errno = 0;
    if (syscall(__NR_clock_gettime, CLOCK_REALTIME, &timespec_value) == 0) {
        mask |= CLOCK_DIRECT_SYSCALL;
    }
#endif
    return mask;
}

#if defined(__linux__)
static int install_linux_clock_seccomp(void) {
#if defined(__x86_64__)
    const uint32_t expected_arch = AUDIT_ARCH_X86_64;
#elif defined(__aarch64__)
    const uint32_t expected_arch = AUDIT_ARCH_AARCH64;
#else
    return 78;
#endif

#define DENY_SYSCALL(number)                                                   \
    BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, (uint32_t)(number), 0, 1),            \
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ERRNO | (EPERM & SECCOMP_RET_DATA))

    struct sock_filter filter[] = {
        BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, arch)),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, expected_arch, 1, 0),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_KILL_PROCESS),
        BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, nr)),
#ifdef __NR_clock_gettime
        DENY_SYSCALL(__NR_clock_gettime),
#endif
#ifdef __NR_clock_gettime64
        DENY_SYSCALL(__NR_clock_gettime64),
#endif
#ifdef __NR_gettimeofday
        DENY_SYSCALL(__NR_gettimeofday),
#endif
#ifdef __NR_time
        DENY_SYSCALL(__NR_time),
#endif
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
    };
    const struct sock_fprog program = {
        .len = (unsigned short)(sizeof(filter) / sizeof(filter[0])),
        .filter = filter,
    };
    if (prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0) {
        return 78;
    }
    if (prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, &program) != 0) {
        return 78;
    }
    return 0;
#undef DENY_SYSCALL
}
#endif

static int emit_clock_observation(int install_filter) {
#if defined(__linux__)
    if (install_filter && install_linux_clock_seccomp() != 0) {
        return 78;
    }
#else
    if (install_filter) {
        return 78;
    }
#endif
    const uint32_t mask = clock_observation_mask();
    if (printf("clock_mask=%u\n", mask) < 0) {
        return 78;
    }
    return mask == 0 ? 77 : 0;
}

int main(int argc, char **argv) {
    if (argc != 2 || argv[1] == NULL) {
        return 64;
    }
    if (strcmp(argv[1], "clock-control") == 0) {
        return emit_clock_observation(0);
    }
    if (strcmp(argv[1], "clock-filtered") == 0) {
        return emit_clock_observation(1);
    }
    return 64;
}
