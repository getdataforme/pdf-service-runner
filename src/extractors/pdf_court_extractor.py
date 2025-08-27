#!/usr/bin/env python3
"""
PDF Court Document Extractor
Simple, class-based PDF extraction for court documents

Extracts:
- Incident date
- PDF file name  
- County name
- Additional case details
"""

import os
import json
import csv
import pdfplumber
from difflib import SequenceMatcher
from pdfminer.high_level import extract_text, extract_pages
from pdfminer.layout import LTTextBox, LTTextLine
from typing import Dict, List, Any, Optional
from datetime import datetime
import re
import argparse
from ..utils.database_utils import update_document_with_extraction_results


class PDFCourtExtractor:
    """Main class for extracting court data from PDFs"""

    def __init__(self, patterns_file: str = None):
        """
        Initialize the extractor

        Args:
            patterns_file: Path to JSON file containing extraction patterns
        """
        self.patterns = {}
        self.county = ""
        self.extraction_order = []

        if patterns_file and os.path.exists(patterns_file):
            self.load_patterns(patterns_file)
            
    def normalize_text(self, text: str) -> str:
        """
        Normalize text by converting to lowercase, removing extra whitespace and punctuation.
        
        Args:
            text: The text to normalize
            
        Returns:
            Normalized text string
        """
        text = text.lower()
        
        # Remove extra whitespace and standardize
        text = ' '.join(text.split())
        
        # Remove common punctuation
        for char in '.,;:!?()[]{}"\'\\-_':
            text = text.replace(char, '')
        
        return text

    def load_patterns(self, patterns_file: str):
        """Load extraction patterns from JSON file"""
        with open(patterns_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            self.patterns = data.get('patterns', {})
            self.county = data.get('county', '')
            self.extraction_order = data.get('extraction_order', list(self.patterns.keys()))
            
    def normalize_text(self, text: str) -> str:
        """
        Normalize text by converting to lowercase, removing extra whitespace and punctuation.
        
        Args:
            text: The text to normalize
            
        Returns:
            Normalized text string
        """
        text = text.lower()
        
        # Remove extra whitespace and standardize
        text = ' '.join(text.split())
        
        # Remove common punctuation
        for char in '.,;:!?()[]{}"\'\\-_':
            text = text.replace(char, '')
        
        return text
        
    def extract_plaintiff_contact(self, pdf_path: str) -> Optional[str]:
        """
        Extract plaintiff contact information from a PDF.
        
        Args:
            pdf_path: Local path to the PDF file
            
        Returns:
            Extracted plaintiff contact as a single text string, or None if not found
        """
        try:
            with pdfplumber.open(pdf_path) as pdf:
                full_text = ""
                
                # Extract text from all pages
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        full_text += page_text + "\n"
                
                # Trigger phrases for finding contact info
                trigger_phrases = [
                    "PLAINTIFF HEREBY DEMANDSA JURYTRIAL ON ALL ISSUES SO TRIABLE.",
                    "Plaintiff demands trial by jury on all issues triable as of right."
                ]
                alternative_triggers = [
                    "jury demand",
                    "jury trial demanded",
                    "plaintiff demands",
                    "plaintiff hereby demands"
                ]
                all_triggers = trigger_phrases + alternative_triggers
                
                # Find trigger by checking line by line
                trigger_index = -1
                all_lines = full_text.split('\n')
                cumulative_length = 0
                
                for line in all_lines:
                    # Check exact match first
                    found_exact = False
                    for phrase in all_triggers:
                        if phrase.lower() in line.lower():
                            trigger_index = cumulative_length + line.lower().find(phrase.lower())
                            found_exact = True
                            break
                    
                    if found_exact:
                        break
                        
                    # If no exact match, try fuzzy matching
                    normalized_line = self.normalize_text(line)
                    for phrase in all_triggers:
                        normalized_phrase = self.normalize_text(phrase)
                        similarity = SequenceMatcher(None, normalized_phrase, normalized_line).ratio()
                        if similarity > 0.8:
                            trigger_index = cumulative_length
                            found_exact = True
                            break
                    
                    if found_exact:
                        break
                        
                    # Add line length plus newline character for cumulative position tracking
                    cumulative_length += len(line) + 1
                
                if trigger_index == -1:
                    return None
                
                # Get the contact text after the trigger
                contact_text = full_text[trigger_index:trigger_index + 500]
                
                # Clean the contact text
                cleaned_contact = self.clean_contact(contact_text)
                
                # Join the cleaned contact lines into a single string
                if cleaned_contact:
                    result = "\n".join(cleaned_contact)
                    return result
                
                return None
                
        except Exception as e:
            print(f"Error extracting plaintiff contact: {str(e)}")
            return None
    
    def clean_contact(self, text: str) -> List[str]:
        """
        Clean the extracted contact text by removing unwanted lines and cutoff at certain terms.
        
        Args:
            text: The raw extracted contact text
            
        Returns:
            List of cleaned contact text lines
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
            line = line.strip()
            if not line:
                continue
                
            line_lower = line.lower()
            if any(term in line_lower for term in remove_terms):
                continue  # skip this line entirely
            if any(term in line_lower for term in cutoff_terms):
                break  # stop processing anything further
            result.append(line)
        
        return result

    def extract_text_from_pdf(self, pdf_path: str) -> tuple[str, List[Dict]]:
        """
        Extract text and positional elements from PDF

        Returns:
            tuple: (full_text, text_elements_with_positions)
        """
        full_text = ""
        text_elements = []

        try:
            # Extract full text
            full_text = extract_text(pdf_path)

            # Extract text with positions for advanced matching
            for page_num, page_layout in enumerate(extract_pages(pdf_path)):
                for element in page_layout:
                    if isinstance(element, (LTTextBox, LTTextLine)):
                        x0, y0, x1, y1 = element.bbox
                        text = element.get_text().strip()
                        if text:
                            text_elements.append({
                                'text': text,
                                'x0': x0, 'y0': y0, 'x1': x1, 'y1': y1,
                                'page': page_num
                            })
        except Exception as e:
            raise Exception(f"Error extracting PDF {pdf_path}: {str(e)}")

        return full_text, text_elements

    def extract_from_pdf(self, pdf_path: str, county: str = None) -> Dict[str, Any]:
        """
        Extract data from a single PDF file

        Args:
            pdf_path: Path to PDF file
            county: County name (optional, will use pattern file county if not provided)

        Returns:
            Dictionary with extracted data
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        # Use provided county or fall back to pattern file county
        county_name = county or self.county or "unknown"

        # Extract text from PDF
        full_text, text_elements = self.extract_text_from_pdf(pdf_path)

        # Extract emails automatically
        emails = self._extract_emails({}, full_text)

        # Extract plaintiff contact information
        plaintiff_contact = None
        try:
            plaintiff_contact = self.extract_plaintiff_contact(pdf_path)
            if plaintiff_contact:
                print(f"Successfully extracted plaintiff contact information")
        except Exception as e:
            print(f"Error extracting plaintiff contact: {str(e)}")

        # Initialize results
        results = {
            'pdf_file': os.path.basename(pdf_path),
            'county': county_name,
            'incident_date': None,
            'incident_end_date': None,
            'all_incident_dates': [],
            'emails': emails,
            'plaintiff_contact': plaintiff_contact,
            'extraction_timestamp': datetime.now().isoformat(),
            'extracted_data': {}
        }

        # Extract fields using patterns
        for field_name in self.extraction_order:
            if field_name in self.patterns:
                pattern = self.patterns[field_name]
                value = self._extract_field(pattern, full_text, text_elements)

                if value:
                    results['extracted_data'][field_name] = value

                    # Set incident date if this field contains date information
                    if self._is_date_field(field_name):
                        # Add to all incident dates list
                        standardized_date = self._parse_date_to_standard(value)
                        if standardized_date:
                            incident_info = {
                                'original_date': value,
                                'standard_date': standardized_date,
                                'source_field': field_name,
                                'is_incident': self._is_true_incident_date(field_name, value)
                            }
                            results['all_incident_dates'].append(incident_info)

                        # Set primary incident date (prioritize true incident dates, then longer dates)
                        if not results['incident_date']:
                            results['incident_date'] = value
                            results['incident_source_field'] = field_name
                        elif self._is_true_incident_date(field_name, value) and not self._is_true_incident_date(results.get('incident_source_field', ''), results['incident_date']):
                            # Prefer true incident dates over non-incident dates
                            results['incident_date'] = value
                            results['incident_source_field'] = field_name
                        elif len(value) > len(results['incident_date']) and self._is_true_incident_date(field_name, value) == self._is_true_incident_date(results.get('incident_source_field', ''), results['incident_date']):
                            # Among dates of same type, prefer longer dates
                            results['incident_date'] = value
                            results['incident_source_field'] = field_name

        # After all extractions, determine earliest and latest incident dates
        true_incident_dates = [
            date_info for date_info in results['all_incident_dates'] 
            if date_info.get('is_incident', False) and date_info.get('standard_date')
        ]

        # Also check multiple_dates_extractor for additional dates
        multiple_dates_str = results.get('extracted_data', {}).get('multiple_dates_extractor', '')
        if multiple_dates_str and multiple_dates_str != 'NA':
            # Parse individual dates from multiple_dates_extractor
            parts = multiple_dates_str.split(' | ')
            for part in parts:
                # Extract just the date part, removing context like "(death)"
                date_part = part.split(' (')[0].strip()
                # Skip plain filing dates and common filing date patterns
                if re.match(r'^\d{2}/\d{2}/\d{4}$', date_part):
                    continue
                # Also skip dates that are likely filing dates (July 7, 2025 or July 18, 2025)
                if date_part in ['July 7, 2025', 'July 18, 2025']:
                    continue
                standard_date = self._parse_date_to_standard(date_part)
                if standard_date:
                    # Check if this date is already in true_incident_dates
                    already_exists = any(d['standard_date'] == standard_date for d in true_incident_dates)
                    if not already_exists:
                        # Add this as a true incident date
                        true_incident_dates.append({
                            'original_date': part,  # Keep original with context
                            'standard_date': standard_date,
                            'source_field': 'multiple_dates_extractor',
                            'is_incident': True
                        })

        if true_incident_dates:
            # Sort by standardized date
            true_incident_dates.sort(key=lambda x: x['standard_date'])

            # Set primary incident date to earliest
            earliest = true_incident_dates[0]
            if not results['incident_date'] or earliest['standard_date'] < self._parse_date_to_standard(results['incident_date']):
                results['incident_date'] = earliest['original_date']
                results['incident_source_field'] = earliest['source_field']

            # If multiple incident dates exist, set incident_end_date to latest
            if len(true_incident_dates) > 1:
                latest = true_incident_dates[-1]
                if earliest['standard_date'] != latest['standard_date']:
                    results['incident_end_date'] = latest['original_date']
                    results['incident_end_source_field'] = latest['source_field']

        return results

    def _is_date_field(self, field_name: str) -> bool:
        """Check if field name indicates a date field"""
        date_indicators = [
            'facts_date', 'incident_date', 'contract_date', 
            'accident_date', 'date_of_incident', 'numeric_date',
            'advanced_incident_date', 'contextual_incident_search',
            'fuzzy_incident_date', 'at_time_pattern', 'subject_incident_date',
            'loss_date', 'multiple_dates_extractor'
        ]
        return any(indicator in field_name for indicator in date_indicators)

    def _parse_date_to_standard(self, date_str: str) -> Optional[str]:
        """
        Parse various date formats to standard YYYY-MM-DD format

        Args:
            date_str: Date string in various formats

        Returns:
            Standardized date string or None if parsing fails
        """
        if not date_str:
            return None

        # Clean up the date string
        clean_date = date_str.strip()

        # Remove common prefixes
        prefixes = ['on or about', 'on', 'occurred on', 'happened on']
        for prefix in prefixes:
            if clean_date.lower().startswith(prefix.lower()):
                clean_date = clean_date[len(prefix):].strip()

        # Try different date parsing patterns
        date_patterns = [
            # MM/DD/YYYY
            (r'(\d{1,2})/(\d{1,2})/(\d{4})', lambda m: f"{m.group(3)}-{m.group(1):0>2}-{m.group(2):0>2}"),
            # Month DD, YYYY (with optional ordinals)
            (r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})', 
             lambda m: f"{m.group(3)}-{self._month_to_number(m.group(1)):0>2}-{m.group(2):0>2}"),
            # DD-MM-YYYY or MM-DD-YYYY
            (r'(\d{1,2})-(\d{1,2})-(\d{4})', lambda m: f"{m.group(3)}-{m.group(1):0>2}-{m.group(2):0>2}"),
        ]

        for pattern, formatter in date_patterns:
            match = re.search(pattern, clean_date, re.IGNORECASE)
            if match:
                try:
                    return formatter(match)
                except:
                    continue

        return None

    def _month_to_number(self, month_name: str) -> int:
        """Convert month name to number"""
        months = {
            'january': 1, 'february': 2, 'march': 3, 'april': 4,
            'may': 5, 'june': 6, 'july': 7, 'august': 8,
            'september': 9, 'october': 10, 'november': 11, 'december': 12
        }
        return months.get(month_name.lower(), 1)

    def _standardize_multiple_dates(self, multiple_dates_str: str) -> str:
        """Convert multiple dates string to standardized format"""
        if not multiple_dates_str or multiple_dates_str == "NA":
            return ""

        dates = []
        parts = multiple_dates_str.split(' | ')
        for part in parts:
            # Extract just the date part, removing context like "(death)"
            date_part = part.split(' (')[0].strip()
            standard_date = self._parse_date_to_standard(date_part)
            if standard_date:
                dates.append(standard_date)

        return ' | '.join(dates)

    def _is_true_incident_date(self, source_field: str, date_str: str) -> bool:
        """
        Determine if the extracted date is a true incident date vs other dates (filing, etc.)

        Args:
            source_field: The field name where the date was extracted from
            date_str: The actual date string

        Returns:
            True if this appears to be an actual incident date
        """
        # True incident date indicators
        incident_indicators = [
            'facts_date', 'incident_date', 'accident_date'
        ]

        # Non-incident date indicators (these are typically filing/administrative dates)
        non_incident_indicators = [
            'filed_date', 'filing_date'
        ]

        # Check if it's clearly a non-incident date
        if any(indicator in source_field for indicator in non_incident_indicators):
            # However, if the date string contains incident context, it might still be an incident date
            incident_context = ['on or about', 'occurred on', 'happened on', 'incident on']
            if any(context in date_str.lower() for context in incident_context):
                return True
            return False

        # Check if it's clearly an incident date
        if any(indicator in source_field for indicator in incident_indicators):
            return True

        # If date string contains incident context words, likely an incident date
        incident_context = ['on or about', 'occurred on', 'happened on']
        if any(context in date_str.lower() for context in incident_context):
            return True

        # Special cases for likely filing dates
        filing_date_indicators = [
            'numeric_date', 'multiple_dates_extractor', 'advanced_incident_date'
        ]

        # If it's a pattern that could be filing date and has no incident context, likely filing
        if (source_field in filing_date_indicators and 
            not any(context in date_str.lower() for context in ['on or about', 'occurred', 'happened', 'incident', 'accident', 'collision'])):
            return False

        # Special case: plain numeric dates like "07/07/2025" without context are likely filing dates
        if re.match(r'^\d{2}/\d{2}/\d{4}$', date_str.strip()):
            return False

        # Default to True for ambiguous cases (most court docs are about incidents)
        return True

    def _extract_field(self, pattern: Dict[str, Any], full_text: str, 
                      text_elements: List[Dict]) -> Optional[str]:
        """
        Extract field based on pattern type

        Pattern Types:
        - 'regex': Direct regex pattern matching
        - 'nearest_word': Find text near keywords
        - 'section_pattern': Extract text between keywords
        - 'facts_pattern': Extract dates from facts sections
        - 'email': Extract email addresses
        """
        pattern_type = pattern.get('type', '')

        if pattern_type == 'regex':
            return self._extract_with_regex(pattern, full_text)
        elif pattern_type == 'nearest_word':
            return self._extract_nearest_word(pattern, text_elements)
        elif pattern_type == 'section_pattern':
            return self._extract_section(pattern, full_text)
        elif pattern_type == 'facts_pattern':
            return self._extract_facts_date(pattern, full_text)
        elif pattern_type == 'case_title':
            return self._extract_case_title(pattern, full_text)
        elif pattern_type == 'fuzzy_date':
            return self._extract_fuzzy_date(pattern, full_text)
        elif pattern_type == 'contextual_search':
            return self._extract_contextual_search(pattern, full_text)
        elif pattern_type == 'multi_pattern':
            return self._extract_multi_pattern(pattern, full_text)
        elif pattern_type == 'multi_date':
            return self._extract_multiple_dates(pattern, full_text)
        elif pattern_type == 'email':
            return self._extract_emails(pattern, full_text)

        return None

    def _extract_with_regex(self, pattern: Dict[str, Any], full_text: str) -> Optional[str]:
        """Extract using regex pattern"""
        regex = pattern.get('regex', '')
        if not regex:
            return None

        match = re.search(regex, full_text, re.IGNORECASE)
        if match:
            # Always return the full match instead of individual groups
            # This prevents returning just "June" when the full match is "June 17th, 2025"
            full_match = match.group(0)

            # If there are captured groups, check if any group is longer than the full match
            # This handles cases where we want the captured group instead
            if match.groups():
                for group in match.groups():
                    if group and len(group) > len(full_match):
                        return group

            return full_match

        return None

    def _extract_nearest_word(self, pattern: Dict[str, Any], 
                             text_elements: List[Dict]) -> Optional[str]:
        """Extract text near keywords using positional data"""
        keywords = pattern.get('keywords', [])
        position = pattern.get('position', 'right')
        max_distance = pattern.get('max_distance', 150)
        extract_words = pattern.get('extract_words', 1)

        for keyword in keywords:
            for i, elem in enumerate(text_elements):
                if keyword.lower() in elem['text'].lower():
                    # Found keyword, look for nearby text
                    result_words = []

                    if position == 'right':
                        # Look for text to the right
                        for j in range(i + 1, min(i + 20, len(text_elements))):
                            next_elem = text_elements[j]

                            # Check if on same page and approximately same line
                            if (next_elem['page'] == elem['page'] and 
                                abs(next_elem['y0'] - elem['y0']) < 10 and
                                next_elem['x0'] - elem['x1'] < max_distance):

                                result_words.append(next_elem['text'])
                                if len(result_words) >= extract_words:
                                    break

                    if result_words:
                        result = " ".join(result_words)

                        # Apply additional cleaning
                        extract_until = pattern.get('extract_until', [])
                        for delimiter in extract_until:
                            pos = result.find(delimiter)
                            if pos != -1:
                                result = result[:pos]
                                break

                        return result.strip()

        return None

    def _extract_section(self, pattern: Dict[str, Any], full_text: str) -> Optional[str]:
        """Extract text between start and end keywords"""
        start_keywords = pattern.get('start_keywords', [])
        end_keywords = pattern.get('end_keywords', [])

        text_lower = full_text.lower()

        # Find start position
        start_pos = -1
        for keyword in start_keywords:
            pos = text_lower.find(keyword.lower())
            if pos != -1:
                start_pos = pos + len(keyword)
                break

        if start_pos == -1:
            return None

        # Find end position
        end_pos = len(full_text)
        for keyword in end_keywords:
            pos = text_lower.find(keyword.lower(), start_pos)
            if pos != -1 and pos < end_pos:
                end_pos = pos

        if start_pos < end_pos:
            return full_text[start_pos:end_pos].strip()

        return None

    def _extract_facts_date(self, pattern: Dict[str, Any], full_text: str) -> Optional[str]:
        """Extract date from facts section using pattern"""
        keywords = pattern.get('keywords', [])
        date_regex = pattern.get('date_regex', '')

        if not date_regex:
            return None

        for keyword in keywords:
            keyword_pos = full_text.lower().find(keyword.lower())
            if keyword_pos != -1:
                # Look for date pattern nearby
                search_start = max(0, keyword_pos - 50)
                search_end = min(len(full_text), keyword_pos + 200)
                search_text = full_text[search_start:search_end]

                date_match = re.search(date_regex, search_text, re.IGNORECASE)
                if date_match:
                    return date_match.group(1) if date_match.groups() else date_match.group(0)

        return None

    def _extract_case_title(self, pattern: Dict[str, Any], full_text: str) -> Optional[str]:
        """Extract case title/description"""
        keywords = pattern.get('keywords', ['vs.', 'v.', 'versus'])

        for keyword in keywords:
            if keyword in full_text:
                # Find text around the keyword
                pos = full_text.find(keyword)
                start = max(0, pos - 100)
                end = min(len(full_text), pos + 100)

                text_segment = full_text[start:end]

                # Extract line containing the keyword
                lines = text_segment.split('\n')
                for line in lines:
                    if keyword in line:
                        # Clean up the line
                        title = line.strip()
                        # Remove case number if present
                        title = re.sub(r'\d{4}-[A-Z]{2}-\d{6}-[A-Z]', '', title).strip()
                        if title and len(title) > 5:
                            return title

        return None

    def _extract_fuzzy_date(self, pattern: Dict[str, Any], full_text: str) -> Optional[str]:
        """
        Extract dates with fuzzy matching - handles variations in spacing, punctuation, etc.
        """
        base_patterns = pattern.get('base_patterns', [])
        context_keywords = pattern.get('context_keywords', [])

        # Create variations of the base patterns
        all_patterns = []
        for base_pattern in base_patterns:
            # Add variations with different spacing and punctuation
            variations = [
                base_pattern,
                base_pattern.replace('\\s+', '\\s*'),  # Optional spaces
                base_pattern.replace(',', '[,.]?'),     # Optional comma or period
                base_pattern.replace(':', '[:\\-\\s]*') # Various separators
            ]
            all_patterns.extend(variations)

        # Search near context keywords if provided
        if context_keywords:
            for keyword in context_keywords:
                keyword_pos = full_text.lower().find(keyword.lower())
                if keyword_pos != -1:
                    # Search in a window around the keyword
                    search_start = max(0, keyword_pos - 200)
                    search_end = min(len(full_text), keyword_pos + 300)
                    search_text = full_text[search_start:search_end]

                    for pattern_regex in all_patterns:
                        try:
                            match = re.search(pattern_regex, search_text, re.IGNORECASE)
                            if match:
                                return self._extract_best_match(match)
                        except re.error:
                            continue  # Skip invalid regex patterns

        # Fallback to global search
        for pattern_regex in all_patterns:
            try:
                match = re.search(pattern_regex, full_text, re.IGNORECASE)
                if match:
                    return self._extract_best_match(match)
            except re.error:
                continue  # Skip invalid regex patterns

        return None

    def _extract_contextual_search(self, pattern: Dict[str, Any], full_text: str) -> Optional[str]:
        """
        Enhanced contextual search with scoring and confidence
        """
        primary_keywords = pattern.get('primary_keywords', [])
        secondary_keywords = pattern.get('secondary_keywords', [])
        target_patterns = pattern.get('target_patterns', [])
        search_radius = pattern.get('search_radius', 250)

        best_match = None
        best_score = 0

        # Find all potential contexts
        contexts = []
        for primary in primary_keywords:
            for match in re.finditer(re.escape(primary), full_text, re.IGNORECASE):
                start_pos = match.start()
                contexts.append({
                    'keyword': primary,
                    'position': start_pos,
                    'context_start': max(0, start_pos - search_radius),
                    'context_end': min(len(full_text), start_pos + search_radius)
                })

        # Score each context
        for context in contexts:
            context_text = full_text[context['context_start']:context['context_end']]
            score = 1  # Base score for primary keyword

            # Add points for secondary keywords
            for secondary in secondary_keywords:
                if secondary.lower() in context_text.lower():
                    score += 0.5

            # Search for target patterns in this context
            for target_pattern in target_patterns:
                try:
                    match = re.search(target_pattern, context_text, re.IGNORECASE)
                    if match:
                        if score > best_score:
                            best_score = score
                            best_match = self._extract_best_match(match)
                except re.error:
                    continue  # Skip invalid regex patterns

        return best_match

    def _extract_multi_pattern(self, pattern: Dict[str, Any], full_text: str) -> Optional[str]:
        """
        Try multiple patterns in priority order and return the best match
        """
        patterns = pattern.get('patterns', [])
        scoring = pattern.get('scoring', {})

        candidates = []

        for i, pattern_info in enumerate(patterns):
            pattern_regex = pattern_info.get('regex', '')
            weight = pattern_info.get('weight', 1.0)

            try:
                matches = list(re.finditer(pattern_regex, full_text, re.IGNORECASE))
            except re.error:
                continue  # Skip invalid regex patterns

            for match in matches:
                extracted = self._extract_best_match(match)
                if extracted:
                    # Score based on pattern priority, match quality, and context
                    score = weight * (len(patterns) - i)  # Higher priority = higher score

                    # Bonus for longer matches (more specific)
                    score += len(extracted) * 0.1

                    # Bonus for incident-related context
                    context_start = max(0, match.start() - 100)
                    context_end = min(len(full_text), match.end() + 100)
                    context = full_text[context_start:context_end].lower()

                    incident_keywords = ['incident', 'accident', 'occurred', 'happened', 'facts']
                    context_bonus = sum(0.2 for keyword in incident_keywords if keyword in context)
                    score += context_bonus

                    candidates.append({
                        'text': extracted,
                        'score': score,
                        'pattern_index': i
                    })

        if candidates:
            # Return the highest scored candidate
            best_candidate = max(candidates, key=lambda x: x['score'])
            return best_candidate['text']

        return None

    def _extract_best_match(self, match) -> str:
        """Extract the best representation from a regex match"""
        if match.groups():
            # Find the longest non-empty group
            groups = [g for g in match.groups() if g]
            if groups:
                return max(groups, key=len)
        return match.group(0)

    def _extract_multiple_dates(self, pattern: Dict[str, Any], full_text: str) -> str:
        """
        Extract multiple dates from document and return as structured summary
        """
        date_patterns = pattern.get('date_patterns', [])
        context_radius = pattern.get('context_radius', 50)
        incident_indicators = pattern.get('incident_indicators', [])

        all_dates = []
        seen_standardized_dates = set()  # Track standardized dates to avoid duplicates

        # Find all dates with their contexts
        for date_pattern in date_patterns:
            try:
                for match in re.finditer(date_pattern, full_text, re.IGNORECASE):
                    date_text = match.group(0)
                    start_pos = match.start()
                    end_pos = match.end()

                    # Skip filing dates (MM/DD/YYYY format without context)
                    if re.match(r'^\d{2}/\d{2}/\d{4}$', date_text.strip()):
                        continue  # Skip plain filing dates

                    # Standardize the date to check for duplicates
                    standardized_date = self._parse_date_to_standard(date_text)
                    if standardized_date and standardized_date in seen_standardized_dates:
                        continue  # Skip duplicate dates

                    if standardized_date:
                        seen_standardized_dates.add(standardized_date)

                    # Extract context around the date
                    context_start = max(0, start_pos - context_radius)
                    context_end = min(len(full_text), end_pos + context_radius)
                    context = full_text[context_start:context_end].lower()

                    # Score based on incident indicators in context
                    incident_score = 0
                    found_indicators = []
                    for indicator in incident_indicators:
                        if indicator.lower() in context:
                            incident_score += 1
                            found_indicators.append(indicator)

                    all_dates.append({
                        'date': date_text,
                        'standardized_date': standardized_date,
                        'position': start_pos,
                        'context': context.replace('\n', ' ').strip(),
                        'incident_score': incident_score,
                        'indicators': found_indicators
                    })
            except re.error:
                continue

        # Sort by incident score (highest first) then by position
        all_dates.sort(key=lambda x: (-x['incident_score'], x['position']))

        # Return summary of top unique dates
        if all_dates:
            summary_parts = []
            for i, date_info in enumerate(all_dates[:3]):  # Top 3 unique dates
                if date_info['incident_score'] > 0:
                    indicators_str = ', '.join(date_info['indicators'][:2])  # First 2 indicators
                    summary_parts.append(f"{date_info['date']} ({indicators_str})")
                else:
                    summary_parts.append(date_info['date'])

            return ' | '.join(summary_parts)

        return None

    def _extract_emails(self, pattern: Dict[str, Any], full_text: str) -> Optional[str]:
        """
        Extract email addresses from PDF text

        Returns a comma-separated string of unique email addresses found
        """
        import re   

        # Standard email regex pattern
        EMAIL_REGEX = re.compile(r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b')

        # Find all email addresses
        found_emails = EMAIL_REGEX.findall(full_text)

        if found_emails:
            # Remove duplicates and sort
            unique_emails = sorted(set(found_emails))

            # Optional: Apply additional validation or filtering
            valid_emails = []
            for email in unique_emails:
                # Basic validation - skip obviously invalid emails
                if len(email) > 5 and '.' in email.split('@')[1]:
                    valid_emails.append(email)

            if valid_emails:
                return ', '.join(valid_emails)

        return None

    def extract_batch(self, pdf_folder: str, county: str = None, 
                     save_individual: bool = True, update_mongodb: bool = True) -> List[Dict[str, Any]]:
        """
        Extract from all PDFs in a folder

        Args:
            pdf_folder: Path to folder containing PDFs
            county: County name
            save_individual: Whether to save individual results
            update_mongodb: Whether to update MongoDB with extraction results

        Returns:
            List of extraction results
        """
        if not os.path.exists(pdf_folder):
            raise FileNotFoundError(f"PDF folder not found: {pdf_folder}")

        pdf_files = [f for f in os.listdir(pdf_folder) if f.endswith('.pdf')]
        results = []

        # Load PDF to Document ID mapping if it exists
        mapping_file = os.path.join(pdf_folder, "pdf_to_docid_mapping.json")
        pdf_mapping = {}
        if os.path.exists(mapping_file):
            try:
                with open(mapping_file, 'r', encoding='utf-8') as f:
                    pdf_mapping = json.load(f)
                print(f"Loaded PDF to Document ID mapping with {len(pdf_mapping)} entries")
            except Exception as e:
                print(f"Warning: Could not load PDF mapping file: {e}")

        print(f"Found {len(pdf_files)} PDF files to process")
        print(f"PDF mapping keys: {list(pdf_mapping.keys())}")

        for pdf_file in pdf_files:
            pdf_path = os.path.join(pdf_folder, pdf_file)
            print(f"Processing: {pdf_file}")

            try:
                result = self.extract_from_pdf(pdf_path, county)

                # Find matching entry in PDF mapping (handle filename variations)
                mapping_key = None
                mapping_data = None

                # First try exact match
                if pdf_file in pdf_mapping:
                    mapping_key = pdf_file
                    mapping_data = pdf_mapping[pdf_file]
                else:
                    # Try to find a match where the current pdf_file ends with a key from mapping
                    for key in pdf_mapping:
                        if pdf_file.endswith(key):
                            mapping_key = key
                            mapping_data = pdf_mapping[key]
                            break

                # Add MongoDB document ID if available
                if mapping_data:
                    print(f"Found mapping for {pdf_file} using key: {mapping_key}")
                    result['mongo_doc_id'] = mapping_data['doc_id']
                    result['original_gcs_path'] = mapping_data['original_path']

                results.append(result)

                # Update MongoDB if enabled and document ID is available
                if update_mongodb and mapping_data:
                    print("updating mongodb document with the pdf extracted data")
                    self._update_mongodb_document(result, mapping_data['doc_id'])

                if save_individual:
                    self._save_individual_result(result)


            except Exception as e:
                print(f"Error processing {pdf_file}: {e}")
                error_result = {
                    'pdf_file': pdf_file,
                    'county': county or 'unknown',
                    'error': str(e)
                }

                # Find matching entry in PDF mapping for error case too
                mapping_data = None
                if pdf_file in pdf_mapping:
                    mapping_data = pdf_mapping[pdf_file]
                else:
                    # Try to find a match where the current pdf_file ends with a key from mapping
                    for key in pdf_mapping:
                        if pdf_file.endswith(key):
                            mapping_data = pdf_mapping[key]
                            break

                if mapping_data:
                    error_result['mongo_doc_id'] = mapping_data['doc_id']

                results.append(error_result)

        # Save batch results
        self._save_batch_results(results, county or 'batch')
        return results

    def _save_individual_result(self, result: Dict[str, Any]):
        """Save individual extraction result"""
        county_name = result.get('county', 'unknown')
        output_dir = os.path.join('outputs', county_name)
        os.makedirs(output_dir, exist_ok=True)

        pdf_name = os.path.splitext(result['pdf_file'])[0]
        output_file = os.path.join(output_dir, f"{pdf_name}.json")

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

    def _update_mongodb_document(self, result: Dict[str, Any], doc_id: str):
        """Update MongoDB document with extraction results"""

        try:
            success = update_document_with_extraction_results(doc_id, result)

            if success:
                print(f"✓ Updated MongoDB document {doc_id} with extraction results")
            else:
                print(f"✗ Failed to update MongoDB document {doc_id}")

            return success

        except Exception as e:
            print(f"Error updating MongoDB document {doc_id}: {e}")
            return False

    def _save_batch_results(self, results: List[Dict[str, Any]], county: str):
        """Save batch results as JSON and CSV"""
        os.makedirs('outputs', exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Save JSON
        json_file = os.path.join('outputs', f"{county}_batch_{timestamp}.json")
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        # Save CSV summary
        csv_file = os.path.join('outputs', f"{county}_summary_{timestamp}.csv")
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['PDF File', 'County', 'MongoDB Doc ID', 'Incident Date', 'Incident End Date', 'Standard Incident Date', 'Standard Incident End Date', 'Is Incident', 'All Dates Count', 'Multiple Dates', 'Standard Multiple Dates', 'Emails', 'Status'])

            for result in results:
                if 'error' in result:
                    writer.writerow([result['pdf_file'], result['county'], '', '', '', '', '', '', '', '', '', '', f"ERROR: {result['error']}"])
                else:
                    original_date = result.get('incident_date', '')
                    end_date = result.get('incident_end_date', '')
                    standard_date = self._parse_date_to_standard(original_date) if original_date else ''
                    standard_end_date = self._parse_date_to_standard(end_date) if end_date else ''
                    source_field = result.get('incident_source_field', '')
                    is_incident = self._is_true_incident_date(source_field, original_date) if original_date else False

                    # Check if we only found filing dates (no true incident dates)
                    all_dates = result.get('all_incident_dates', [])
                    has_true_incident = any(date_info.get('is_incident', False) for date_info in all_dates)

                    # Additional check: if the primary date is just a plain MM/DD/YYYY with no context, treat as no incident
                    if original_date and re.match(r'^\d{2}/\d{2}/\d{4}$', original_date.strip()):
                        has_true_incident = False

                    if not has_true_incident:
                        original_date = "NA"
                        end_date = ""
                        standard_date = "NA"
                        standard_end_date = ""
                        is_incident = False

                    # Get multiple dates info
                    all_dates = result.get('all_incident_dates', [])
                    dates_count = len(all_dates)
                    multiple_dates_summary = result.get('extracted_data', {}).get('multiple_dates_extractor', '')

                    # If no true incident dates found, set multiple dates to NA as well
                    if not has_true_incident:
                        multiple_dates_summary = "NA"

                    # Create standardized version of multiple dates
                    standard_multiple_dates = self._standardize_multiple_dates(multiple_dates_summary)

                    # Get emails
                    emails = result.get('emails', '')

                    writer.writerow([
                        result['pdf_file'],
                        result['county'], 
                        original_date,
                        end_date,
                        standard_date,
                        standard_end_date,
                        'True' if is_incident else 'False',
                        dates_count,
                        multiple_dates_summary[:100] + '...' if len(multiple_dates_summary) > 100 else multiple_dates_summary,
                        standard_multiple_dates,
                        emails,
                        'Success'
                    ])

        print(f"Results saved:")
        print(f"  JSON: {json_file}")
        print(f"  CSV:  {csv_file}")
