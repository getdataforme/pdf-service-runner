pdf_path = r"E:\Jyaba\legaldatamanagerpdfservice\temp_individual_pdfs\Complaint4.pdf"

from typing import Dict, Optional, List
from difflib import SequenceMatcher
from typing import Optional, Dict, List
import pdfplumber
from difflib import SequenceMatcher

def extract_plaintiff_contact_with_layout(pdf_path: str) -> Optional[List[Dict]]:
    """
    Extract plaintiff contact info from PDF, returning text with alignment/bbox.
    Returns a list of dicts with line-by-line layout information.
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            full_text = ""
            all_chars = []
            char_to_page = []  # Track which page each character belongs to

            # Collect all characters with their page info
            for page_idx, page in enumerate(pdf.pages):
                chars = page.chars
                if chars:
                    all_chars.extend(chars)
                    char_to_page.extend([page_idx] * len(chars))
                page_text = page.extract_text()
                if page_text:
                    full_text += page_text + "\n"

            # Trigger phrases
            trigger_phrases = [
                "PLAINTIFF HEREBY DEMANDSA JURYTRIAL ON ALL ISSUES SO TRIABLE.",
                "Plaintiff demands trial by jury on all issues triable as of right."
            ]
            alternative_triggers = []
            all_triggers = trigger_phrases + alternative_triggers

            # Find trigger by checking line by line
            trigger_index = -1
            all_lines = full_text.split('\n')
            cumulative_length = 0
            
            for line in all_lines:
                # Check exact match first
                found_exact = False
                for phrase in all_triggers:
                    if phrase in line:
                        trigger_index = cumulative_length + line.find(phrase)
                        found_exact = True
                        break
                
                if found_exact:
                    break
                    
                # If no exact match, try fuzzy matching
                normalized_line = normalize_text(line)
                for phrase in all_triggers:
                    normalized_phrase = normalize_text(phrase)
                    similarity = SequenceMatcher(None, normalized_phrase, normalized_line).ratio()
                    if similarity > 0.8:
                        print(f"Fuzzy match found: '{line}' matches '{phrase}' with similarity {similarity:.2f}")
                        trigger_index = cumulative_length
                        found_exact = True
                        break
                
                if found_exact:
                    break
                    
                # Add line length plus newline character for cumulative position tracking
                cumulative_length += len(line) + 1
            
            if trigger_index == -1:
                print("No trigger phrases found in document")
                return None

            # Get the contact text
            contact_text = full_text[trigger_index:trigger_index + 500]
            
            result = clean_contact(contact_text)

            return result

    except Exception as e:
        print(f"Error: {e}")
        return None

def clean_contact(text):
    """
    Remove lines containing keywords like 'HEREBY', 'DEMANDS', 'JURY', 'TRIAL', 
    'ISSUES', 'TRIABLE', 'Respectfully', 'submitted', 'this'.
    If a line contains cutoff terms like 'Attorneys for Plaintiff', 'Benefits', 
    'Explanation', 'PATIENT', 'TRANSACTION', 'HISTORY', 'CHARGES',
    then keep nothing after that line.
    """
    result = []
    cutoff_terms = [
        'attorneys for plaintiff', 'benefits', 'explanation', 
        'patient', 'transaction', 'history', 'charges'
    ]
    remove_terms = [
        'hereby', 'demands', 'jury', 'trial', 
        'issues', 'triable', 'respectfully', 'submitted', 'this'
    ]

    for line in text.split('\n'):
        line_lower = line.lower()
        if any(term in line_lower for term in remove_terms):
            continue  # skip this line entirely
        if any(term in line_lower for term in cutoff_terms):
            break  # stop processing anything further
        result.append(line)

    return result


def normalize_text(text: str) -> str:
    text = text.lower()
    
    # Remove extra whitespace and standardize
    text = ' '.join(text.split())
    
    # Remove common punctuation
    for char in '.,;:!?()[]{}"\'\\-_':
        text = text.replace(char, '')
    
    return text



# Example usage
if __name__ == "__main__":    
    result = extract_plaintiff_contact_with_layout(pdf_path)