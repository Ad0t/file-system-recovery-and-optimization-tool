import math

class Disk:
    def __init__(self, total_blocks=1000, block_size=4096):
        self.total_blocks = total_blocks
        self.block_size = block_size
        self.blocks = {}

    def read_block(self, block_num):
        return self.blocks.get(block_num, "")

    def write_block(self, block_num, data):
        self.blocks[block_num] = data


class SimpleFileSystem:
    def __init__(self, disk):
        self.disk = disk
        self.free_blocks = list(range(disk.total_blocks))
        self.files = {}

    def create_file(self, filename, data):
        num_blocks_needed = math.ceil(len(data) / self.disk.block_size)
        if len(data) == 0:
            num_blocks_needed = 1
            
        blocks_allocated = []
        for _ in range(num_blocks_needed):
            block_num = self.free_blocks.pop(0)
            blocks_allocated.append(block_num)
            
        self.files[filename] = blocks_allocated
        
        for i, block_num in enumerate(blocks_allocated):
            start = i * self.disk.block_size
            end = start + self.disk.block_size
            chunk = data[start:end]
            self.disk.write_block(block_num, chunk)

    def read_file(self, filename):
        if filename not in self.files:
            return ""
        
        result_data = ""
        for block_num in self.files[filename]:
            result_data += self.disk.read_block(block_num)
        return result_data

    def delete_file(self, filename):
        if filename in self.files:
            for block_num in self.files[filename]:
                self.free_blocks.append(block_num)
                self.disk.write_block(block_num, "")
            del self.files[filename]

    def list_files(self):
        return list(self.files.keys())


if __name__ == "__main__":
    # Create a file system with 100 blocks
    # Using a small block size (16 bytes) so our short strings span multiple blocks
    disk = Disk(total_blocks=100, block_size=16)
    fs = SimpleFileSystem(disk)

    print("--- Creating 3 files ---")
    fs.create_file("doc1.txt", "This is the first document. It has a bit of text.")
    fs.create_file("doc2.txt", "Tiny file")
    fs.create_file("doc3.txt", "The quick brown fox jumps over the lazy dog. A slightly longer string here.")

    print("\n--- Listing files ---")
    for f in fs.list_files():
        print(f'- {f} (Blocks: {fs.files[f]})')

    print("\n--- Reading files back ---")
    print(f"doc1.txt: '{fs.read_file('doc1.txt')}'")
    print(f"doc2.txt: '{fs.read_file('doc2.txt')}'")
    print(f"doc3.txt: '{fs.read_file('doc3.txt')}'")

    print("\n--- Deleting doc2.txt ---")
    fs.delete_file("doc2.txt")

    print("\n--- Listing files after deletion ---")
    for f in fs.list_files():
        print(f'- {f} (Blocks: {fs.files[f]})')
    
    print("\n--- Free Blocks Count ---")
    print(f"{len(fs.free_blocks)} blocks available out of {disk.total_blocks}")
