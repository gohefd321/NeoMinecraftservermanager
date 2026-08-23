#include <tunables/global>

profile minecraft-secure flags=(attach_disconnected,mediate_deleted) {
  #include <abstractions/base>
  #include <abstractions/nameservice>

  # 1. Capabilities 제한: JVM 및 네트워크 바인딩에 필요한 최소 권한만 허용
  capability net_bind_service,
  capability setgid,
  capability setuid,
  deny capability sys_admin,
  deny capability sys_ptrace,
  deny capability sys_module,
  deny capability sys_rawio,
  deny capability sys_boot,
  deny capability dac_override,
  deny capability dac_read_search,

  # 2. 민감한 호스트 시스템 디렉토리 접근 차단 (RCE 및 정보 탈취 방어)
  deny /proc/kcore rwklx,
  deny /proc/sys/** rwklx,
  deny /sys/** rwklx,
  deny /etc/shadow* rwklx,
  deny /etc/gshadow* rwklx,
  deny /etc/sudoers* rwklx,
  deny /root/** rwklx,
  deny /dev/mem rwklx,
  deny /dev/kmem rwklx,
  deny /dev/port rwklx,

  # 3. 마인크래프트 데이터 디렉토리 (/data) 읽기/쓰기/생성/잠금 허용
  /data/ rw,
  /data/** rwk,

  # 4. Java 런타임 및 라이브러리 실행 권한 (Read & Execute)
  /opt/java/** rix,
  /usr/lib/jvm/** rix,
  /usr/bin/java rix,
  /bin/sh rix,
  /bin/bash rix,

  # 5. 임시 런타임 디렉토리 허용
  /tmp/** rwk,
  /var/tmp/** rwk,

  # 6. 네트워크 소켓 및 루프백 통신
  network inet stream,
  network inet dgram,
  network inet6 stream,
  network inet6 dgram,
  network netlink raw,
}
