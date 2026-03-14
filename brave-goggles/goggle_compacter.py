import os
import re
from collections import defaultdict
from typing import List

def validate_instruction(instruction: str) -> bool:
    """Evaluates string against strict character and operator limits."""
    if len(instruction) > 500: return False
    if instruction.count('*') > 2: return False
    if instruction.count('^') > 2: return False
    return True

def merge_regex_nodes(rules: List[str]) -> List[str]:
    """
    Synthesizes discrete rules into regex alternations based on isomorphic prefixes.
    Targets path boundaries ('/') for split evaluation.
    """
    prefixes = defaultdict(list)
    optimized_matrix = []
    
    for rule in rules:
        if rule.startswith('/') or rule.startswith('$') or len(rule) < 10:
            optimized_matrix.append(rule)
            continue
            
        parts = rule.split('/', 1)
        if len(parts) == 2:
            prefixes[parts[0]].append(parts[1])
        else:
            optimized_matrix.append(rule)
            
    for prefix, suffixes in prefixes.items():
        if len(suffixes) > 1:
            escaped_prefix = re.escape(prefix)
            joined_suffixes = "|".join(re.escape(s) for s in suffixes)
            merged_rule = f"/{escaped_prefix}\\/({joined_suffixes})/"
            
            if validate_instruction(merged_rule):
                optimized_matrix.append(merged_rule)
            else:
                optimized_matrix.extend([f"{prefix}/{s}" for s in suffixes])
        else:
            optimized_matrix.append(f"{prefix}/{suffixes[0]}")
            
    return optimized_matrix

def execute_chunking(input_file: str, output_prefix: str = "optimized_goggles"):
    """
    Executes physical file partitioning bound by byte and integer constraints.
    Max Bytes: 2MB. Max Lines: 100,000.
    """
    MAX_LINES = 100000
    MAX_BYTES = 2 * 1000 * 1000
    
    valid_rules = []
    if not os.path.exists(input_file):
        raise FileNotFoundError("Target .goggles file absent from directory.")

    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            clean_line = line.strip()
            if not clean_line or clean_line.startswith('!'): continue
            if validate_instruction(clean_line):
                valid_rules.append(clean_line)
                
    compiled_rules = merge_regex_nodes(valid_rules)
    
    chunk_index = 1
    current_lines = 0
    current_bytes = 0
    file_pointer = None
    
    def initialize_partition():
        nonlocal file_pointer, chunk_index, current_lines, current_bytes
        if file_pointer: file_pointer.close()
        file_pointer = open(f"{output_prefix}_part{chunk_index}.goggles", 'w', encoding='utf-8')
        chunk_index += 1
        current_lines = 0
        current_bytes = 0
        
    initialize_partition()
    
    for rule in compiled_rules:
        encoded_rule = rule.encode('utf-8')
        rule_byte_size = len(encoded_rule) + 1 
        
        if current_lines >= MAX_LINES or (current_bytes + rule_byte_size) > MAX_BYTES:
            initialize_partition()
            
        file_pointer.write(rule + '\n')
        current_lines += 1
        current_bytes += rule_byte_size
        
    if file_pointer:
        file_pointer.close()

if __name__ == "__main__":
    # TARGET_LOCK: Replace with local system filepath.
    execute_chunking("top-1m.goggles")