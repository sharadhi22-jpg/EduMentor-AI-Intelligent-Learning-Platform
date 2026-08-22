class RecursiveCharacterChunker:
    """
    A custom recursive character splitter designed to split long documents into 
    contextual chunks with overlap. It splits recursively using paragraph, newline,
    space, and character boundaries, mimicking LangChain's RecursiveCharacterTextSplitter.
    """
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = ["\n\n", "\n", " ", ""]

    def chunk_text(self, text: str) -> list[str]:
        if not text:
            return []
        return self._split_text(text, self.separators)

    def _split_text(self, text: str, separators: list[str]) -> list[str]:
        final_chunks = []
        
        # Base case: if text is small enough, return it
        if len(text) <= self.chunk_size:
            return [text.strip()]

        # Determine which separator to use
        separator = separators[-1]
        new_separators = []
        for idx, sep in enumerate(separators):
            if sep == "":
                separator = sep
                break
            if sep in text:
                separator = sep
                new_separators = separators[idx + 1:]
                break

        # Split text by selected separator
        if separator != "":
            splits = text.split(separator)
        else:
            splits = list(text)

        splits = [s for s in splits if s]

        current_doc = []
        current_len = 0

        for split in splits:
            split_len = len(split)
            
            # If a single split is larger than the chunk size, we must split it recursively
            if split_len > self.chunk_size:
                if current_doc:
                    final_chunks.append(self._merge_splits(current_doc, separator))
                    current_doc = []
                    current_len = 0
                
                # Recursively split the long block
                if new_separators:
                    recursive_splits = self._split_text(split, new_separators)
                    final_chunks.extend(recursive_splits)
                else:
                    # No separators left, hard slice the string
                    for i in range(0, split_len, self.chunk_size - self.chunk_overlap):
                        final_chunks.append(split[i : i + self.chunk_size])
            else:
                # Check if we can fit the split into the current accumulator
                needed_sep_len = len(separator) if current_doc else 0
                if current_len + split_len + needed_sep_len <= self.chunk_size:
                    current_doc.append(split)
                    current_len += split_len + needed_sep_len
                else:
                    # Finalize current chunk
                    if current_doc:
                        final_chunks.append(self._merge_splits(current_doc, separator))
                    
                    # Backtrack to build the overlapping segment
                    overlap_doc = []
                    overlap_len = 0
                    for prev_split in reversed(current_doc):
                        prev_len = len(prev_split)
                        needed_overlap_sep = len(separator) if overlap_doc else 0
                        if overlap_len + prev_len + needed_overlap_sep <= self.chunk_overlap:
                            overlap_doc.insert(0, prev_split)
                            overlap_len += prev_len + needed_overlap_sep
                        else:
                            break
                    
                    current_doc = overlap_doc
                    current_doc.append(split)
                    current_len = sum(len(x) for x in current_doc) + len(separator) * (len(current_doc) - 1)

        if current_doc:
            final_chunks.append(self._merge_splits(current_doc, separator))

        # Return unique non-empty chunks
        return [c for c in final_chunks if c]

    def _merge_splits(self, splits: list[str], separator: str) -> str:
        return separator.join(splits).strip()
