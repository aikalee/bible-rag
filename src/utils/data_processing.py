from bs4 import BeautifulSoup
import csv
import io
import json
import pickle
import requests
import re

def get_content(subpath):

    url = f"https://enduringword.com/bible-commentary/{subpath}/"
    response = requests.get(url)

    if response.status_code != 200:
        raise BlockingIOError(f"Scraping {subpath} failed. Status code: {response.status_code}")

    soup = BeautifulSoup(response.text, "html.parser")

    # find div.avia_textblock with h3
    selectors = [
        "div.avia_textblock:has(h3):not(:has(h3 i)):not(:has(h3 em))",
        "div.avia_textblock:has(h3)"
    ]

    forbidden_words = ("Video", "Audio")
    target_tags = {"h3", "p"}

    output = None
    filtered = []

    for selector in selectors:
        candidates = soup.select(selector)

        if len(candidates) == 1:
            output = candidates[0]
            break

        elif len(candidates) > 1:
            
            filtered = [
                tag for tag in candidates
                if all(word not in tag.get_text() for word in forbidden_words)
            ]

            if len(filtered) == 1:
                output = filtered[0]
                break

            elif not filtered:
                continue  # try next selector

            else:
                continue  # try next selector

    if not output:

        if not filtered:
            raise ValueError("No valid content found from selectors.")
        
        raise ValueError(f"Multiple content blocks found after filtering: {len(filtered)}")
    


    # Try to find a layer (self or child <div>) that contains both <h3> and <p>
    for layer in (output, output.find("div")):

        if not layer:
            continue

        child_tags = {child.name for child in layer.contents if getattr(child, "name", None)}
        
        if target_tags.issubset(child_tags):
            output = layer
            break
    else:
        raise ValueError("No layer contains both <h3> and <p> tags together.")

        
    return output


def parse_content(subpath, content, doc_id):

    matched = re.search(r"(.+)-(\d+)", subpath)
    if not matched:
        raise ValueError("No matching string.")
    
    book = matched.group(1)
    chapter = matched.group(2)


    cur_h3 = ""
    cur_h4 = ""

    beg = ""
    end = ""

    beg_chapter = ""
    end_chapter = ""

    beg_verse = ""
    end_verse = ""

    docs = []

    verse = []
    commentary = []


    def create_doc():
        nonlocal docs, doc_id

        verse_string = "\n".join(verse)
        commentary_string = "\n".join(commentary)

        title = f"Title: {cur_h3}" if cur_h3 else ""
        subtitle = f"\nSubtitle: {cur_h4}" if cur_h4 else ""
        titled_verse_string = f"\nVerse: {verse_string}" if verse_string else ""

        text_block = title + subtitle + titled_verse_string 

        doc = {
                "text": text_block,
                "metadata": {
                    "doc_id": doc_id,
                    "title": cur_h3,
                    "subtitle": cur_h4,
                    "commentary": commentary_string,
                    "verse": verse_string,
                    "book": book,
                    "beg_verse": beg,
                    "end_verse": end
                },
            }
        
        docs.append(doc)
        doc_id += 1
    
    def extract_number(string):
        nonlocal beg, end, beg_chapter, end_chapter, beg_verse, end_verse

        pattern = r"(?=.*[:\(\)])(?:(\d+)[ab]?\b(?!\.)\:)?(?:(\d+)[ab]?\b(?!\.))"
            
        verse_number = re.findall(pattern, string)
            
        
        if len(verse_number)%2 == 1:
                
            if len(verse_number[0]) != 2:
                raise ValueError("There must be two groups in a matching string.")
            
            grp1, grp2 = verse_number[0]

            
            beg_chapter = grp1 or ""
            end_chapter = grp1 or ""
            
            
            beg_verse = grp2 or ""
            end_verse = grp2 or ""

        
        elif len(verse_number) != 0:

            # Extract only the first 2 matches
            match1, match2 = verse_number[:2]

            if any(x != 2 for x in (len(match1), len(match2))):
                raise ValueError("There must be two groups in each matching string.")
            
            grp1_1, grp1_2 = match1
            grp2_1, grp2_2 = match2

            beg_chapter = grp1_1 or ""
            beg_verse = grp1_2 or ""
            
            end_chapter = grp2_1 or ""
            end_verse = grp2_2 or ""
            

        if beg_chapter and end_chapter:
            beg = beg_chapter + ":" + beg_verse
            end = end_chapter + ":" + end_verse
        
        elif beg_chapter:
            beg = beg_chapter + ":" + beg_verse
            end = beg_chapter + ":" + end_verse

        else:
            beg = chapter + ":" + beg_verse
            end = chapter + ":" + end_verse

        

    # Paragraphs under the same h4 as a chunk
    for child in content.children:
        

        if child.name == "h3":
            
            if cur_h3:
                # === Only if h4 is absent ===
                if not cur_h4:
                    create_doc()
                    verse = []
                    commentary = []

            cur_h3 = child.get_text()
            extract_number(cur_h3)

            

        if child.name == "h4":

            if cur_h4:
                create_doc()
                verse = []
                commentary = []
                
            cur_h4 = child.get_text()
            extract_number(cur_h4)

            

        if child.name == "p":

            if child.has_attr("class"):
               
                if child.get("class")[0] in ["p1", "s1"]:
                
                    create_doc()
                    verse = []
                    commentary = []
                else:
                    raise ValueError("The document does not end with <p> with attribute class p1 or s1.")
         
            elif child.has_attr("style"):
                
                if child.get("style").startswith(("padding-left", "text-align")):
                    commentary.append(child.get_text())
                else:
                    raise ValueError("There is a <p> with styles other than padding-left and text-align.")
            
            else:
                verse.append(child.get_text())
        
        if child.name == "table":
            
            rows = child.find_all("tr")

            table_data = []

            for row in rows:
               
                cells = row.find_all(["th", "td"])
                
                row_data = [cell.get_text(strip=True) for cell in cells]
                table_data.append(row_data)

            csv_buffer = io.StringIO()
            writer = csv.writer(csv_buffer)
            writer.writerows(table_data)

            csv_text = csv_buffer.getvalue()
            commentary.append(f"Here is a csv table:\r\n{csv_text}")           
                
    return docs, doc_id
         

def to_json(read_path, write_path):

    all_docs = []
    doc_id = 1

    with open(read_path, "rb") as f:
        chapter_list = pickle.load(f)

    for chapter in chapter_list:
        content = get_content(chapter)
        docs, doc_id = parse_content(chapter, content, doc_id)
        all_docs.extend(docs)
    
    with open(write_path, "w", encoding="utf-8") as f:
        json.dump(all_docs, f, indent=4)


def main():
    READ_PATH = "../../data/chapter_list.pkl"
    WRITE_PATH = "../../data/commentary.json"
    
    to_json(READ_PATH, WRITE_PATH)


if __name__ == "__main__":
    main()
