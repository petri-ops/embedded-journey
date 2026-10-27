"""给 MicroPython ESP32_GENERIC_S3-SPIRAM_OCT v1.29.0 固件打 XMC Flash 启动补丁。

背景：ESP-IDF v5.5.2 的 bootloader 只把 RDID 型号字节 0x40/0x41/0x50 的 XMC Flash
视为合法芯片。本板 Flash 为 20 70 18（型号字节 0x70，16MB），启动流程复查时误判
XMC 启动失败并重启（日志：bootloader_flash: XMC flash startup fail）。

补丁只改一处：把该函数失败分支的返回值 ESP_FAIL(-1) 改为 ESP_OK(0)，保留 XMC
启动流程本身；随后重算镜像 checksum 与 SHA256（ROM 会校验，不改会拒载）。

用法：python patch_xmc_207018.py <官方原始 bin> <输出 bin>
"""

import hashlib
import sys

SEGMENTS = [(0x0020, 0x0EAC), (0x0ED4, 0x0C28), (0x1B04, 0x2FF8)]
PATCH_AT = 0x231D  # VA 0x403CBF19: movi.n a2, -1 -> movi.n a2, 0
CHECKSUM_AT = 0x4AFF
HASH_AT = 0x4B00


def patch(src: str, dst: str) -> None:
    raw = bytearray(open(src, "rb").read())
    assert raw[0] == 0xE9, "不是 ESP 镜像"
    assert raw[PATCH_AT:PATCH_AT + 2] == b"\x7c\xf2", "补丁点不匹配（固件版本不同？）"

    raw[PATCH_AT:PATCH_AT + 2] = b"\x0c\x02"

    checksum = 0xEF
    for off, length in SEGMENTS:
        for b in raw[off:off + length]:
            checksum ^= b
    raw[CHECKSUM_AT] = checksum

    raw[HASH_AT:HASH_AT + 32] = hashlib.sha256(bytes(raw[:HASH_AT])).digest()

    open(dst, "wb").write(raw)
    print(f"patched -> {dst} (checksum 0x{checksum:02X})")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    patch(sys.argv[1], sys.argv[2])
