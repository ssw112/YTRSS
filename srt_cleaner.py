import re

def parse_srt(srt_path):
    with open(srt_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Split into blocks
    blocks = content.strip().split("\n\n")
    clean_lines = []
    
    for block in blocks:
        lines = block.split("\n")
        if len(lines) < 3:
            continue
        
        # Subtitle lines are starting from index 2 in each SRT block
        for line in lines[2:]:
            line_stripped = line.strip()
            # Ignore empty lines, music tags, and purely duplicate consecutive lines
            if not line_stripped or line_stripped == "[Music]":
                continue
            
            # Clean off basic duplicates in the block or immediate history
            if not clean_lines or clean_lines[-1] != line_stripped:
                clean_lines.append(line_stripped)
                
    # Join and strip down duplicate repeating words (e.g. "We're no strangers to We're no strangers to")
    full_text = " ".join(clean_lines)
    
    # Simple regex to deduplicate consecutive identical word sequences (up to 4 words)
    # This cleans up the ASR triple-repetition pattern very nicely!
    deduped = re.sub(r'\b(\w+(?:\s+\w+){0,3})\s+\1\b', r'\1', full_text, flags=re.IGNORECASE)
    
    # Repeat once more for nested repetitions
    deduped = re.sub(r'\b(\w+(?:\s+\w+){0,3})\s+\1\b', r'\1', deduped, flags=re.IGNORECASE)
    
    return deduped
