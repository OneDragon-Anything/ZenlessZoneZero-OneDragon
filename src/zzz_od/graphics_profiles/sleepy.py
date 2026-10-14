import io
import struct

from pathlib import Path
from enum import Enum
from typing import List, Tuple, Union


# https: // github.com / dotnet / runtime / blob / a7efcd9ca9255dc9faa8b4a2761cdfdb62619610 / src / libraries / System.Runtime.Serialization.Formatters / src / System / Runtime / Serialization / Formatters / Binary / BinaryEnums.cs  # L7C1-L32C6
class BinaryHeaderEnum(Enum):
    SerializedStreamHeader = 0
    Object = 1
    ObjectWithMap = 2
    ObjectWithMapAssemId = 3
    ObjectWithMapTyped = 4
    ObjectWithMapTypedAssemId = 5
    ObjectString = 6
    Array = 7
    MemberPrimitiveTyped = 8
    MemberReference = 9
    ObjectNull = 10
    MessageEnd = 11
    Assembly = 12
    ObjectNullMultiple256 = 13
    ObjectNullMultiple = 14
    ArraySinglePrimitive = 15
    ArraySingleObject = 16
    ArraySingleString = 17
    CrossAppDomainMap = 18
    CrossAppDomainString = 19
    CrossAppDomainAssembly = 20
    MethodCall = 21
    MethodReturn = 22
    BinaryReference = -1


# https: // github.com / dotnet / runtime / blob / a7efcd9ca9255dc9faa8b4a2761cdfdb62619610 / src / libraries / System.Runtime.Serialization.Formatters / src / System / Runtime / Serialization / Formatters / Binary / BinaryEnums.cs  # L35
class BinaryTypeEnum(Enum):
    Primitive = 0
    String = 1
    Object = 2
    ObjectUrt = 3
    ObjectUser = 4
    ObjectArray = 5
    StringArray = 6
    PrimitiveArray = 7


# https: // github.com / dotnet / runtime / blob / a7efcd9ca9255dc9faa8b4a2761cdfdb62619610 / src / libraries / System.Runtime.Serialization.Formatters / src / System / Runtime / Serialization / Formatters / Binary / BinaryEnums.cs  # L47
class BinaryArrayTypeEnum(Enum):
    Single = 0
    Jagged = 1
    Rectangular = 2
    SingleOffset = 3
    JaggedOffset = 4
    RectangularOffset = 5


# https: // github.com / dotnet / runtime / blob / a7efcd9ca9255dc9faa8b4a2761cdfdb62619610 / src / libraries / System.Runtime.Serialization.Formatters / src / System / Runtime / Serialization / Formatters / Binary / BinaryEnums.cs  # L99
class InternalArrayTypeE(Enum):
    Empty = 0
    Single = 1
    Jagged = 2
    Rectangular = 3
    Base64 = 4


class BinaryReader:
    def __init__(self, stream):
        self.stream = stream

    def read_byte(self):
        byte = self.stream.read(1)
        if not byte:
            raise EOFError("End of stream reached")
        return byte[0]

    def read_int32(self):
        bytes_read = self.stream.read(4)
        if len(bytes_read) < 4:
            raise EOFError("End of stream reached")
        return struct.unpack('<i', bytes_read)[0]

    def read_7_bit_encoded_int(self):
        result = 0
        max_bytes_without_overflow = 4

        for shift in range(0, max_bytes_without_overflow * 7, 7):
            byte_read_just_now = self.read_byte()
            result |= (byte_read_just_now & 0x7F) << shift

            if byte_read_just_now <= 0x7F:
                return result  # Early exit

        # Read the 5th byte
        byte_read_just_now = self.read_byte()
        if byte_read_just_now > 0b1111:
            raise ValueError("Bad 7-bit encoded integer format")

        result |= byte_read_just_now << (max_bytes_without_overflow * 7)
        return result

    def log_assert_info_byte_enum(self, assert_header_enum):
        current_int = self.read_byte()
        self.log_assert_info(assert_header_enum, current_int)

    def log_assert_info_int32_enum(self, assert_header_enum):
        current_int = self.read_int32()
        self.log_assert_info(assert_header_enum, current_int)

    def log_assert_info(self, assert_header_enum, current_int: int):
        int_assert_casted = assert_header_enum.value
        if int_assert_casted != current_int:
            assert_header_enum_value_name = assert_header_enum.name
            compared_enum_casted = BinaryHeaderEnum(current_int)
            compared_header_enum_value_name = compared_enum_casted.name
            raise ValueError(
                f"[Sleepy::LogAssertInfo] BinaryFormatter header is not valid at stream pos: {self.stream.tell():x}. "
                f"Expecting object enum: {assert_header_enum_value_name} but getting: {compared_header_enum_value_name} instead!")

    def get_binary_formatter_data_length(self) -> int:
        return self.read_7_bit_encoded_int()

    def emulate_sleepy_binary_formatter_header_assertion(self):
        # Check if the first byte is SerializedStreamHeader
        self.log_assert_info_byte_enum(BinaryHeaderEnum.SerializedStreamHeader)

        # Check if the type is an Object
        self.log_assert_info_int32_enum(BinaryHeaderEnum.Object)

        # Check if the type is a BinaryReference
        self.log_assert_info_int32_enum(BinaryHeaderEnum.BinaryReference)

        # Check if the BinaryReference type is a String
        self.log_assert_info_int32_enum(BinaryTypeEnum.String)

        # Check for the binary array type and check if it's Single
        self.log_assert_info_int32_enum(BinaryArrayTypeEnum.Single)

        # Check for the binary type and check if it's StringArray (UTF-8)
        self.log_assert_info_byte_enum(BinaryTypeEnum.StringArray)

        # Check for the internal array type and check if it's Single
        self.log_assert_info_int32_enum(InternalArrayTypeE.Single)

    def emulate_sleepy_binary_formatter_footer_assertion(self):
        self.log_assert_info_byte_enum(BinaryHeaderEnum.MessageEnd)


class BinaryWriter:
    def __init__(self, stream):
        self.stream = stream

    def write(self, data):
        if isinstance(data, bytes):
            self.stream.write(data)
        elif isinstance(data, int):
            self.stream.write(struct.pack('<i', data))
        elif isinstance(data, bytearray):
            self.stream.write(data)
        else:
            raise ValueError("Unsupported data type")

    def write_enum_as_byte(self, header_enum):
        enum_value = header_enum.value
        self.write(bytes([enum_value]))

    def write_enum_as_int32(self, header_enum):
        enum_value = header_enum.value
        self.write(enum_value)

    def write_7_bit_encoded_int(self, value):
        while value >= 0x80:
            self.write(bytes([(value | 0x80) & 0xff]))
            value >>= 7
        self.write(bytes([value & 0xff]))

    def emulate_sleepy_binary_formatter_header_write(self):
        self.write_enum_as_byte(BinaryHeaderEnum.SerializedStreamHeader)
        self.write_enum_as_int32(BinaryHeaderEnum.Object)
        self.write_enum_as_int32(BinaryHeaderEnum.BinaryReference)
        self.write_enum_as_int32(BinaryTypeEnum.String)
        self.write_enum_as_int32(BinaryArrayTypeEnum.Single)
        self.write_enum_as_byte(BinaryTypeEnum.StringArray)
        self.write_enum_as_int32(InternalArrayTypeE.Single)

    def emulate_sleepy_binary_formatter_footer_write(self):
        self.write_enum_as_byte(BinaryHeaderEnum.MessageEnd)


class JsonSerializer:
    def __init__(self,
                 indent: Union[None, str, int] = 4,
                 separators: Tuple[str, str] = (',', ':'),
                 newline: str = '\r\n'):

        if isinstance(indent, int):
            self.indent = ' ' * indent
        elif isinstance(indent, str):
            self.indent = indent
        elif indent is None:
            self.indent = ''
        else:
            raise ValueError(f'Indent option {indent} has unsupported type {type(indent)}!')
        self.item_separator = separators[0]
        self.key_separator = separators[1]
        self.newline = newline

    def dumps(self, obj):
        return self.newline + self.dump_value(obj)

    def dump_value(self, value, level: int = 0) -> str:
        if isinstance(value, str):
            return '"' + value.replace('\\', '\\\\').replace('\"', '\\\"') + '"'
        elif isinstance(value, bool):
            return 'true' if value else 'false'
        elif value is None:
            return 'null'
        elif isinstance(value, int):
            return str(value)
        elif isinstance(value, float):
            return str(value).replace(',', '.')
        elif isinstance(value, list):
            return self.dump_list(value, level + 1)
        elif isinstance(value, dict):
            return self.dump_dict(value, level + 1)
        else:
            raise ValueError(f'Value {value} has unsupported type {type(value)}!')

    def dump_list(self, src_list: list, level: int) -> str:
        result = '[' + self.newline

        for element_id, value in enumerate(src_list):
            is_last_element = element_id == len(src_list) - 1
            item_separator = '' if is_last_element else self.item_separator
            value = self.dump_value(value, level)
            result += f'{self.indent*level}{value}{item_separator}{self.newline}'

        result += self.indent * (level - 1) + ']'

        return result

    def dump_dict(self, src_dict: dict, level: int) -> str:
        result = '{' + self.newline

        max_key_len = 0
        for element_id, (key, value) in enumerate(src_dict.items()):
            max_key_len = len(key) if len(key) > max_key_len else max_key_len
            spacing = max_key_len - len(key) + 1
            is_last_element = element_id == len(src_dict) - 1
            item_separator = '' if is_last_element else self.item_separator
            value = self.dump_value(value, level)
            result += f'{self.indent*level}"{key}"{" " * spacing}{self.key_separator} {value}{item_separator}{self.newline}'

        result += self.indent * (level - 1) + '}'

        return result


class Sleepy:

    def read_file(self, path: Path, magic: bytes) -> str:
        with open(path, 'rb') as f:
            stream = io.BytesIO(f.read())
            return self.read_string(stream, magic)

    def write_file(self, path: Path, magic: bytes, content: str):
        with open(path, 'wb') as f:
            stream = io.BytesIO()
            self.write_string(stream, content, magic)
            f.write(stream.getbuffer())

    @staticmethod
    def create_evil(magic: bytes) -> tuple:
        magic_length = len(magic)
        evilist = [False] * magic_length
        evils_count = 0

        for i in range(magic_length):
            n = i % magic_length
            evilist[i] = (magic[n] & 0xC0) == 0xC0
            if evilist[i]:
                evils_count += 1

        return evilist, evils_count

    @staticmethod
    def internal_decode(magic: bytes, evil, reader, length, magic_length, bp) -> int:
        eepy = False
        j = 0
        i = 0

        while i < length:
            n = i % magic_length
            c = reader.read(1)
            if not c:
                break
            c = c[0]
            ch = c ^ magic[n]

            if evil[n]:
                eepy = ch != 0
            else:
                if eepy:
                    ch += 0x40
                    eepy = False
                j += 1
                bp[j] = chr(ch)

            i += 1

        return j + len(bp)

    @staticmethod
    def internal_write(magic: bytes, content_len: int, content_bytes: bytearray, encoded_bytes: bytearray, magic_evil: List[bool]) -> int:
        h = 0
        i = 0
        j = 0

        while j < content_len:
            n = i % len(magic)
            ch = content_bytes[j]

            if magic_evil[n]:
                eepy = 0
                if ch > 0x40:
                    ch -= 0x40
                    eepy = 1

                encoded_bytes[h] = (eepy ^ magic[n]) & 0xFF
                h += 1
                i += 1
                n = i % len(magic)

            encoded_bytes[h] = (ch ^ magic[n]) & 0xFF
            h += 1
            i += 1
            j += 1

        return h

    def read_string(self, stream: io.BytesIO, magic: bytes) -> str:
        # Assert stream
        if not stream.readable():
            raise ValueError("[Sleepy::ReadString] Stream must be readable!")

        cnt = ['{:02x}'.format(x) for x in stream.read()]
        stream.seek(0)

        # Create wrapper over stream that emulates C# binary reader
        reader = BinaryReader(stream)

        # Consume header bytes and assert header integrity
        reader.emulate_sleepy_binary_formatter_header_assertion()

        # Consume data length bytes
        length = reader.get_binary_formatter_data_length()

        # Calculate magic length
        magic_length = len(magic)

        # Allocate temporary buffer
        buffer_chars = [''] * length

        # Create evil
        evil, evils_count = self.create_evil(magic)

        j = self.internal_decode(magic, evil, stream, length, magic_length, buffer_chars)

        # Consume footer bytes and assert footer integrity
        reader.emulate_sleepy_binary_formatter_footer_assertion()

        return ''.join(buffer_chars[:j])

    def write_string(self, stream: io.BytesIO, content: str, magic: bytes):
        # Stream assertion
        if not stream.writable():
            raise ValueError("[Sleepy::WriteString] Stream must be writable!")

        # Magic assertion
        if len(magic) == 0:
            raise ValueError("[Sleepy::WriteString] Magic cannot be empty!")

        # Assign the writer
        writer = BinaryWriter(stream)

        # Emulate header write
        writer.emulate_sleepy_binary_formatter_header_write()

        # Do the do
        content_len = len(content)
        buffer_len = content_len * 2

        # Alloc temporary buffers
        content_bytes = bytearray(buffer_len)
        encoded_bytes = bytearray(buffer_len)

        # Create evil
        evil, evils_count = self.create_evil(magic)

        # Convert string to bytes (UTF-8 encoding)
        content_bytes[:content_len] = content.encode('utf-8')

        # Do the do (pt. 2)
        h = self.internal_write(magic, content_len, content_bytes, encoded_bytes, evil)

        # Write length and encoded bytes to stream
        writer.write_7_bit_encoded_int(h)  # Assuming h is meant to be written as an int32.
        writer.write(encoded_bytes[:h])

        # Emulate footer write
        writer.emulate_sleepy_binary_formatter_footer_write()
