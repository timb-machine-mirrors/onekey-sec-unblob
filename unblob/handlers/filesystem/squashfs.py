import io
from typing import List, Optional

from structlog import get_logger

from ...file_utils import Endian, convert_int32, round_up
from ...models import StructHandler, ValidChunk

logger = get_logger()

PAD_SIZE = 4_096
BIG_ENDIAN_MAGIC = 0x73_71_73_68


class _SquashFSBase(StructHandler):
    @staticmethod
    def make_extract_command(inpath: str, outdir: str) -> List[str]:
        return ["unsquashfs", "-f", "-d", outdir, inpath]


class SquashFSv3Handler(_SquashFSBase):
    NAME = "squashfs_v3"

    YARA_RULE = r"""
        strings:
            /**
            00000000  73 71 73 68 00 00 00 03  00 00 00 00 00 00 00 00  |sqsh............|
            00000010  00 00 00 00 00 00 00 00  00 00 00 00 00 03 00 00  |................|
            */
            $squashfs_v3_magic_be = { 73 71 73 68 [24] 00 03}

            /**
            00000000  68 73 71 73 03 00 00 00  00 00 00 00 00 00 00 00  |hsqs............|
            00000010  00 00 00 00 00 00 00 00  00 00 00 00 03 00 00 00  |................|
            */
            $squashfs_v3_magic_le = { 68 73 71 73 [24] 03 00}

        condition:
            $squashfs_v3_magic_le or $squashfs_v3_magic_be
    """

    C_DEFINITIONS = r"""
        struct SQUASHFS3_SUPER_BLOCK
        {
            char   s_magic[4];
            uint32 inodes;
            uint32 bytes_used_2;
            uint32 uid_start_2;
            uint32 guid_start_2;
            uint32 inode_table_start_2;
            uint32 directory_table_start_2;
            uint16 s_major;
            uint16 s_minor;
            uint16 block_size_1;
            uint16 block_log;
            uint8  flags;
            uint8  no_uids;
            uint8  no_guids;
            uint32 mkfs_time /* time of filesystem creation */;
            uint64 root_inode;
            uint32 block_size;
            uint32 fragments;
            uint32 fragment_table_start_2;
            int64  bytes_used;
            int64  uid_start;
            int64  guid_start;
            int64  inode_table_start;
            int64  directory_table_start;
            int64  fragment_table_start;
            int64  lookup_table_start;
        };
    """
    HEADER_STRUCT = "SQUASHFS3_SUPER_BLOCK"

    def calculate_chunk(
        self, file: io.BufferedIOBase, start_offset: int
    ) -> Optional[ValidChunk]:

        # read the magic and derive endianness from it
        magic_bytes = file.read(4)
        magic = convert_int32(magic_bytes, Endian.BIG)
        endian = Endian.BIG if magic == BIG_ENDIAN_MAGIC else Endian.LITTLE

        file.seek(start_offset)
        header = self.parse_header(file, endian)

        size = round_up(header.bytes_used, PAD_SIZE)
        end_offset = start_offset + size

        return ValidChunk(start_offset=start_offset, end_offset=end_offset)


class SquashFSv4Handler(_SquashFSBase):
    NAME = "squashfs_v4"

    YARA_RULE = r"""
        strings:
            /**
            00000000  68 73 71 73 03 00 00 00  00 c1 9c 61 00 00 02 00  |hsqs.......a....|
            00000010  01 00 00 00 01 00 11 00  c0 00 01 00 04 00 00 00  |................|
            */
            $squashfs_v4_magic_le = { 68 73 71 73 [24] 04 00 }

        condition:
            $squashfs_v4_magic_le
    """

    C_DEFINITIONS = r"""
        struct SQUASHFS4_SUPER_BLOCK
        {
            char   s_magic[4];
            uint32 inodes;
            uint32 mkfs_time /* time of filesystem creation */;
            uint32 block_size;
            uint32 fragments;
            uint16 compression;
            uint16 block_log;
            uint16  flags;
            uint16  no_ids;
            uint16 s_major;
            uint16 s_minor;
            uint64 root_inode;
            int64  bytes_used;
            int64  id_table_start;
            int64  xattr_id_table_start;
            int64  inode_table_start;
            int64  directory_table_start;
            int64  fragment_table_start;
            int64  lookup_table_start;
        };
    """
    HEADER_STRUCT = "SQUASHFS4_SUPER_BLOCK"

    def calculate_chunk(
        self, file: io.BufferedIOBase, start_offset: int
    ) -> Optional[ValidChunk]:
        header = self.parse_header(file)
        size = round_up(header.bytes_used, PAD_SIZE)
        end_offset = start_offset + size
        return ValidChunk(start_offset=start_offset, end_offset=end_offset)