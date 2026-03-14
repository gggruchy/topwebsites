import sys
import os
from typing import List, Tuple

def validate_limits(instruction: str) -> bool:
    if len(instruction) > 500: return False
    if instruction.count('*') > 2: return False
    if instruction.count('^') > 2: return False
    return True

def translate_to_regex(token: str) -> str:
    """
    TARGET_LOCK: Custom RE2 structural escape. Bypasses Python's native re.escape
    to prevent strict RE2 parser crashes on hyphens (e.g., \\- in just-eat.co.uk).
    """
    escaped = token.replace('\\', r'\\')
    meta_chars = ['.', '+', '?', '|', '(', ')', '[', ']', '{', '}', '$']
    for char in meta_chars:
        escaped = escaped.replace(char, '\\' + char)
        
    escaped = escaped.replace('*', '.*')
    escaped = escaped.replace('^', r'(?:[^a-zA-Z0-9_%\.-]|$)')
    return escaped

def extract_prefix_suffix(instruction: str) -> Tuple[str, str]:
    if instruction.startswith('/') and instruction.endswith('/'):
        return None, instruction
        
    if any(op in instruction for op in ['||', '@@', '|']) and not instruction.startswith('$'):
        return None, instruction
        
    if instruction.startswith('$') and ',' in instruction:
        directive, target = instruction.split(',', 1)
        if target.startswith('site='):
            return f"{directive},site=", target[len('site='):]
        return f"{directive},", target
        
    if '/' in instruction:
        parts = instruction.split('/', 1)
        return parts[0] + '/', parts[1]
        
    return None, instruction

def pack_regex_nodes(prefix: str, suffixes: List[str]) -> List[str]:
    if not prefix: return suffixes
    
    unique_suffixes = list(dict.fromkeys(suffixes))
    packed_rules = []
    current_group = []
    
    def compile_group(grp: List[str]) -> str:
        is_directive = prefix.startswith('$') and ',' in prefix
        
        # TARGET_LOCK: Output raw ONLY if it's not a directive.
        if len(grp) == 1 and not is_directive:
            return f"{prefix}{grp[0]}"
            
        joined = "|".join(translate_to_regex(s) for s in grp)
        
        # TARGET_LOCK: Force (?:) non-capturing groups to save engine memory.
        # Force regex wrap on all directives (even length 1) to eliminate AST crashes.
        if is_directive:
            directive = prefix.split(',')[0] 
            return f"/(?:{joined})/{directive}"
        elif prefix.endswith('/'):
            base_escaped = translate_to_regex(prefix[:-1])
            return f"/{base_escaped}\\/(?:{joined})/"
        else:
            base_escaped = translate_to_regex(prefix)
            return f"/{base_escaped}(?:{joined})/"

    for suffix in unique_suffixes:
        current_group.append(suffix)
        test_rule = compile_group(current_group)
        
        if not validate_limits(test_rule):
            current_group.pop()
            if current_group:
                packed_rules.append(compile_group(current_group))
            current_group = [suffix]
            
    if current_group:
        packed_rules.append(compile_group(current_group))
        
    return packed_rules

def extract_metadata(filepath: str) -> List[str]:
    meta_block = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            clean = line.strip()
            if not clean: continue
            if clean.startswith('!'): meta_block.append(clean)
            else: break
    return meta_block

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

    def write_rule(rule: str):
        nonlocal current_lines, current_bytes
        rule_bytes = len(rule.encode('utf-8')) + NEWLINE_BYTES
        if current_lines >= MAX_LINES or (current_bytes + rule_bytes) > MAX_BYTES:
            rotate_io()
        file_pointer.write(rule + '\n')
        current_lines += 1
        current_bytes += rule_bytes

    rotate_io()
    
    current_prefix = None
    current_suffixes = []
    
    def flush_buffer():
        if current_suffixes:
            for rule in pack_regex_nodes(current_prefix, current_suffixes):
                write_rule(rule)
            current_suffixes.clear()

    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            clean = line.strip()
            if not clean or clean.startswith('!'): continue
            if not validate_limits(clean): continue

            prefix, suffix = extract_prefix_suffix(clean)
            
            if prefix != current_prefix or len(current_suffixes) > 1000:
                flush_buffer()
                current_prefix = prefix
                
            current_suffixes.append(suffix)
                
    flush_buffer()
    if file_pointer: file_pointer.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("ERROR: EXEC_HALT. Target filename required as ARG[1].")
        sys.exit(1)
        
    execute_tier1_chunking(sys.argv[1])