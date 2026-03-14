import sys
import os
from typing import List

def validate_limits(instruction: str) -> bool:
    if len(instruction) > 500: return False
    if instruction.count('*') > 2: return False
    if instruction.count('^') > 2: return False
    return True

def extract_metadata(filepath: str) -> List[str]:
    meta_block = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            clean = line.strip()
            if not clean: continue
            if clean.startswith('!'): meta_block.append(clean)
            else: break
    return meta_block

def format_instruction(clean_line: str) -> str:
    """
    TARGET_LOCK: Enforces strict Adblock syntax over regex to guarantee
    AST parser acceptance, bypassing the ReDoS complexity ceiling and 
    maximizing engine Trie-hash performance.
    """
    if clean_line.startswith('$discard,'):
        target = clean_line[len('$discard,'):]
        if target.startswith('site='):
            target = target[len('site='):]
        return f"||{target}^$discard"
        
    return clean_line

def execute_tier1_chunking(input_file: str):
    MAX_LINES = 100000
    MAX_BYTES = 1900000 
    NEWLINE_BYTES = len(os.linesep.encode('utf-8'))
    
    if not os.path.exists(input_file):
        print(f"ERROR: Target '{input_file}' not found.")
        sys.exit(1)

    base_metadata = extract_metadata(input_file)
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    chunk_index = 1
    current_lines = 0
    current_bytes = 0
    file_pointer = None
    
    def rotate_io():
        nonlocal file_pointer, chunk_index, current_lines, current_bytes
        if file_pointer: file_pointer.close()
        file_pointer = open(f"{base_name}_part{chunk_index}.goggles", 'w', encoding='utf-8', newline='\n')
        
        current_lines = 0
        current_bytes = 0
        
        for meta in base_metadata:
            mutated_meta = meta
            if meta.lower().startswith('! name:'):
                mutated_meta = f"{meta} (Part {chunk_index})"
                
            rule_bytes = len(mutated_meta.encode('utf-8')) + NEWLINE_BYTES
            file_pointer.write(mutated_meta + '\n')
            current_lines += 1
            current_bytes += rule_bytes
            
        chunk_index += 1

    rotate_io()

    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            clean = line.strip()
            if not clean or clean.startswith('!'): continue
            if not validate_limits(clean): continue

            formatted_rule = format_instruction(clean)
            rule_bytes = len(formatted_rule.encode('utf-8')) + NEWLINE_BYTES
            
            if current_lines >= MAX_LINES or (current_bytes + rule_bytes) > MAX_BYTES:
                rotate_io()
                
            file_pointer.write(formatted_rule + '\n')
            current_lines += 1
            current_bytes += rule_bytes
                
    if file_pointer: file_pointer.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("ERROR: EXEC_HALT. Target filename required as ARG[1].")
        sys.exit(1)
        
    execute_tier1_chunking(sys.argv[1])