import streamlit as st
import json
from typing import Dict, List
import pandas as pd
import google.generativeai as genai
import time
import toml
import os

class JokeManager:
    def __init__(self, jokes_file: str = "jokes.json"):
        self.jokes_file = jokes_file
        try:
            with open(jokes_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Check if data is in new format (with metadata)
                if isinstance(data, dict) and "metadata" in data:
                    self.metadata = data["metadata"]
                    self.jokes = data["jokes"]
                else:
                    # Convert old format
                    self.metadata = {
                        "prompt_template": create_translation_prompt("{{joke_text}}")
                    }
                    self.jokes = data
        except FileNotFoundError:
            self.jokes = {}
            self.metadata = {
                "prompt_template": create_translation_prompt("{{joke_text}}")
            }
    
    def save_jokes(self):
        """Save both jokes and metadata"""
        with open(self.jokes_file, 'w', encoding='utf-8') as f:
            json.dump({
                "metadata": self.metadata,
                "jokes": self.jokes
            }, f, ensure_ascii=False, indent=2)
    
    def update_prompt_template(self, new_template: str):
        """Update the prompt template"""
        self.metadata["prompt_template"] = new_template
        self.save_jokes()
    
    def get_prompt_template(self) -> str:
        """Get current prompt template"""
        return self.metadata.get("prompt_template", create_translation_prompt("{{joke_text}}"))
    
    def get_joke_versions(self, number: str) -> Dict:
        """Get all versions of a specific joke"""
        if number not in self.jokes:
            self.jokes[number] = {
                "original": "",
                "versions": [],
                "status": "pending",
                "rating": 0
            }
        return self.jokes[number]
    
    def add_version(self, number: str, version: str, version_type: str = "simple_hebrew"):
        """Add a new version to a joke"""
        if number not in self.jokes:
            return False
        
        self.jokes[number]["versions"].append({
            "text": version,
            "type": version_type,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        })
        self.save_jokes()
        return True
    
    def get_pending_jokes(self, batch_size: int) -> List[str]:
        """Get a batch of jokes that need translation"""
        return [num for num, joke in self.jokes.items() 
                if joke.get("status", "pending") == "pending"][:batch_size]
    
    def mark_as_deleted(self, number: str):
        """Mark a joke as deleted without actually removing it"""
        if number in self.jokes:
            self.jokes[number]["status"] = "deleted"
            self.save_jokes()
            return True
        return False
    
    def edit_joke(self, number: str, new_text: str, edit_type: str = "edited"):
        """Add edited version of a joke"""
        if number in self.jokes:
            self.jokes[number]["versions"].append({
                "text": new_text,
                "type": edit_type,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            })
            self.save_jokes()
            return True
        return False
    
    def restore_joke(self, number: str):
        """Restore a deleted joke"""
        if number in self.jokes and self.jokes[number]["status"] == "deleted":
            self.jokes[number]["status"] = "pending"
            self.save_jokes()
            return True
        return False
    
    def get_deleted_jokes(self) -> List[tuple[str, Dict]]:
        """Get all deleted jokes"""
        return [(num, joke) for num, joke in self.jokes.items() 
                if joke.get("status") == "deleted"]
    
    def update_rating(self, number: str, is_like: bool):
        """Update joke rating (like +1, dislike -1)"""
        if number in self.jokes:
            self.jokes[number]["rating"] = self.jokes[number].get("rating", 0)
            if is_like:
                self.jokes[number]["rating"] += 1
            else:
                self.jokes[number]["rating"] -= 1
            self.save_jokes()
            return True
        return False
    
    def get_top_jokes(self, limit: int = 10) -> List[tuple[str, Dict]]:
        """Get top rated jokes"""
        sorted_jokes = sorted(
            [(num, joke) for num, joke in self.jokes.items()],
            key=lambda x: x[1].get("rating", 0),
            reverse=True
        )
        return sorted_jokes[:limit]
    
    def add_tag(self, number: str, tag: str):
        """Add a tag to a joke"""
        if number in self.jokes:
            if tag not in self.jokes[number]["tags"]:
                self.jokes[number]["tags"].append(tag)
                self.save_jokes()
                return True
        return False
    
    def remove_tag(self, number: str, tag: str):
        """Remove a tag from a joke"""
        if number in self.jokes:
            if tag in self.jokes[number]["tags"]:
                self.jokes[number]["tags"].remove(tag)
                self.save_jokes()
                return True
        return False
    
    def get_all_tags(self) -> List[str]:
        """Get all unique tags used in jokes"""
        tags = set()
        for joke in self.jokes.values():
            tags.update(joke.get("tags", []))
        return sorted(list(tags))

def load_config():
    """Load configuration from .streamlit/secrets.toml"""
    try:
        return st.secrets["gemini"]
    except Exception as e:
        st.error("Failed to load Gemini API key from secrets.toml")
        return None

def create_gemini_model():
    """Initialize and configure Gemini model"""
    config = load_config()
    if not config:
        return None
        
    genai.configure(api_key=config["api_key"])
    
    generation_config = {
        "temperature": 1,
        "top_p": 0.95,
        "top_k": 40,
        "max_output_tokens": 8192,
    }
    
    return genai.GenerativeModel(
        model_name="gemini-1.5-pro",
        generation_config=generation_config
    )

def create_translation_prompt(joke_text: str) -> str:
    return f"""תרגם את הבדיחה הבאה לעברית פשוטה ומודרנית, שמור על המשמעות והמבנה:

{joke_text}

התרגום צריך:
1. להשתמש בשפה יומיומית ופשוטה
2. להיות ברור וקריא
3. לשמור על ההומור והמשמעות המקורית
4. להימנע ממילים ארכאיות או מליציות

התרגום:"""

def display_joke_side_by_side(joke_data, number, manager):
    """Display joke with original and translation side by side"""
    # Add CSS for buttons
    st.markdown("""
        <style>
            .stButton button {
                width: 100%;
                border-radius: 5px;
                margin: 2px;
            }
            .delete-button button {
                background-color: #ff4b4b;
                color: white;
            }
            .delete-button button:hover {
                background-color: #cc3333;
            }
            .edit-button button {
                background-color: #0096c7;
                color: white;
            }
            .edit-button button:hover {
                background-color: #0077b6;
            }
            .like-button button {
                background-color: #28a745;
                color: white;
            }
            .dislike-button button {
                background-color: #dc3545;
                color: white;
            }
        </style>
    """, unsafe_allow_html=True)
    
    # All buttons in one row
    col_rating_display, col_like, col_dislike, col_edit, col_delete = st.columns([2, 1, 1, 2, 2])
    
    with col_rating_display:
        rating = joke_data.get("rating", 0)
        st.write(f"👥 דירוג: {rating}")
    
    with col_like:
        st.markdown('<div class="like-button">', unsafe_allow_html=True)
        if st.button("👍", key=f"like_{number}"):
            manager.update_rating(number, True)
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col_dislike:
        st.markdown('<div class="dislike-button">', unsafe_allow_html=True)
        if st.button("👎", key=f"dislike_{number}"):
            manager.update_rating(number, False)
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col_edit:
        if joke_data.get("status") != "deleted":
            st.markdown('<div class="edit-button">', unsafe_allow_html=True)
            if st.button("✏️", key=f"edit_{number}"):
                st.session_state[f"editing_{number}"] = True
            st.markdown('</div>', unsafe_allow_html=True)
    
    with col_delete:
        if joke_data.get("status") != "deleted":
            st.markdown('<div class="delete-button">', unsafe_allow_html=True)
            if st.button("🗑️", key=f"delete_{number}"):
                if st.session_state.get(f"confirm_delete_{number}", False):
                    manager.mark_as_deleted(number)
                    st.success("הבדיחה סומנה כמחוקה")
                    st.rerun()
                else:
                    st.session_state[f"confirm_delete_{number}"] = True
                    st.warning("לחץ שוב למחיקה")
            st.markdown('</div>', unsafe_allow_html=True)
        elif joke_data.get("status") == "deleted":
            st.warning("בדיחה מחוקה", icon="🗑️")
    
    # Show edit form if editing
    if st.session_state.get(f"editing_{number}", False):
        with st.form(key=f"edit_form_{number}"):
            edited_text = st.text_area("ערוך ת הבדיחה:", value=joke_data["original"])
            edit_type = st.text_input("סוג העריכה:", value="edited")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.form_submit_button("💾 שמור"):
                    manager.edit_joke(number, edited_text, edit_type)
                    st.session_state[f"editing_{number}"] = False
                    st.success("העריכה נשמרה")
                    st.rerun()
            with col2:
                if st.form_submit_button("❌ בטל"):
                    st.session_state[f"editing_{number}"] = False
                    st.rerun()
    
    # Add tags section after buttons
    st.markdown("---")
    
    # Tags section
    col_tags, col_add = st.columns([4, 1])
    with col_tags:
        if joke_data.get("tags"):
            for tag in joke_data["tags"]:
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(f"🏷️ {tag}")
                with col2:
                    if st.button("❌", key=f"remove_tag_{number}_{tag}"):
                        manager.remove_tag(number, tag)
                        st.rerun()
    
    # Add new tag
    with col_add:
        new_tag = st.text_input("הוסף תגית:", key=f"new_tag_{number}")
        if new_tag:
            if st.button("הוסף", key=f"add_tag_{number}"):
                manager.add_tag(number, new_tag)
                st.rerun()
    
    # Display joke content
    st.markdown("---")  # Separator line
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**גרסה מקורית**")
        if joke_data.get("status") == "deleted":
            st.markdown("~~" + joke_data["original"] + "~~")
        else:
            st.write(joke_data["original"])
    
    with col2:
        if joke_data.get("versions"):
            versions = joke_data["versions"]
            
            # Version navigation
            col_prev, col_curr, col_next = st.columns([1, 3, 1])
            
            # Get current version index from session state
            if f"version_idx_{number}" not in st.session_state:
                st.session_state[f"version_idx_{number}"] = 0
            
            curr_idx = st.session_state[f"version_idx_{number}"]
            
            # Previous version button
            with col_prev:
                if curr_idx > 0:
                    if st.button("⬅️", key=f"prev_{number}"):
                        st.session_state[f"version_idx_{number}"] -= 1
                        st.rerun()
            
            # Current version info
            with col_curr:
                st.markdown(f"**גרסת עריכה {curr_idx + 1} מתוך {len(versions)}**")
            
            # Next version button
            with col_next:
                if curr_idx < len(versions) - 1:
                    if st.button("➡️", key=f"next_{number}"):
                        st.session_state[f"version_idx_{number}"] += 1
                        st.rerun()
            
            # Display current version
            if joke_data.get("status") == "deleted":
                st.markdown("~~" + versions[curr_idx]["text"] + "~~")
            else:
                st.write(versions[curr_idx]["text"])
                st.caption(f'{versions[curr_idx]["type"]} • {versions[curr_idx]["timestamp"]}')
        else:
            st.info("טרם נוצר ��רגום")

def main():
    st.set_page_config(page_title="מאגר הבדיחות", layout="wide")
    
    # Set RTL for the entire app using CSS
    st.markdown("""
        <style>
            .stApp { direction: rtl; }
            .stMarkdown, .stButton, .stTextInput { text-align: right; }
            .version-box {
                border: 1px solid #ddd;
                padding: 10px;
                margin: 5px 0;
                border-radius: 5px;
            }
        </style>
    """, unsafe_allow_html=True)
    
    st.title("מאגר הבדיחות של דרויאנוב")
    
    manager = JokeManager()
    
    # Sidebar for navigation
    st.sidebar.title("אפשרויות")
    mode = st.sidebar.radio(
        "בחר פעולה",
        ["חיפוש בדיחות", "בדיחה לפי מספר", "רשימת בדיחות", 
         "בדיחות מובילות", "ניהול תרגומים", "סל מחזור"]  # Reordered options
    )
    
    if mode == "חיפוש בדיחות":
        st.header("חיפוש בדיחות")
        query = st.text_input("הכנס מילות חיפוש:")
        
        # Add tag filter
        all_tags = manager.get_all_tags()
        selected_tags = st.multiselect("סנן לפי תגיות:", all_tags)
        
        if query or selected_tags:
            results = []
            for number, joke_data in manager.jokes.items():
                # Skip deleted jokes
                if joke_data.get("status") == "deleted":
                    continue
                    
                # Check tags first
                if selected_tags and not any(tag in joke_data.get("tags", []) for tag in selected_tags):
                    continue
                
                # Then check text if query exists
                if query:
                    if query.lower() in joke_data["original"].lower():
                        results.append((number, joke_data))
                        continue
                        
                    for version in joke_data.get("versions", []):
                        if query.lower() in version["text"].lower():
                            results.append((number, joke_data))
                            break
                else:
                    results.append((number, joke_data))
            
            if results:
                # Sort by rating
                results.sort(key=lambda x: x[1].get("rating", 0), reverse=True)
                
                st.write(f"נמצאו {len(results)} תוצאות:")
                for num, joke_data in results:
                    with st.expander(f"בדיחה מספר {num} (דירוג: {joke_data.get('rating', 0)})"):
                        display_joke_side_by_side(joke_data, num, manager)
            else:
                st.warning("לא נמצאו תוצאות")
    
    elif mode == "ניהול תרגומים":
        st.header("ניהול תרגומים")
        
        # Translation settings
        with st.expander("הגדרות תרגום", expanded=True):
            model = create_gemini_model()
            if not model:
                st.error("לא נמצא API key של Gemini ב-secrets.toml")
                return
            
            # Prompt template with save button
            col1, col2 = st.columns([4, 1])
            with col1:
                prompt_template = st.text_area(
                    "תבנית פרומפט:",
                    value=manager.get_prompt_template(),
                    height=300,
                    key="prompt_template"
                )
            with col2:
                if st.button("💾 שמור תבנית"):
                    manager.update_prompt_template(prompt_template)
                    st.success("התבנית נשמרה!")
            
            batch_size = st.number_input("כמות בדיחות לתרגום בבת אחת:", min_value=1, value=5)
        
        # Batch translation
        if st.button("התחל תרגום באצווה"):
            pending_jokes = manager.get_pending_jokes(batch_size)
            if not pending_jokes:
                st.warning("אין בדיחות הממתינות לתרגום")
                return
                
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            chat = model.start_chat(history=[])
            
            for i, joke_number in enumerate(pending_jokes):
                joke = manager.get_joke_versions(joke_number)
                status_text.text(f"מתרגם בדיחה {joke_number}...")
                
                try:
                    # Use saved prompt template
                    prompt = manager.get_prompt_template().replace("{{joke_text}}", joke["original"])
                    response = chat.send_message(prompt)
                    
                    translation = response.text
                    manager.add_version(joke_number, translation)
                    joke["status"] = "completed"
                    manager.save_jokes()
                    
                except Exception as e:
                    st.error(f"שגיאה בתרגום בדיחה {joke_number}: {str(e)}")
                
                progress_bar.progress((i + 1) / len(pending_jokes))
            
            status_text.text("התרגום הושלם!")
    
    elif mode == "בדיחה לפי מספר":
        st.header("בדיחה לפי מספר")
        joke_number = st.text_input("הכנס מספר בדיחה:")
        
        if joke_number:
            joke = manager.get_joke_versions(joke_number)
            if joke:
                st.subheader(f"בדיחה מספר {joke_number}")
                display_joke_side_by_side(joke, joke_number, manager)
                
                # Add new version manually
                with st.expander("הוסף גרסה חדשה"):
                    new_version = st.text_area("טקסט הגרסה:")
                    version_type = st.text_input("סוג הגרסה:", "simple_hebrew")
                    if st.button("שמור גרסה"):
                        manager.add_version(joke_number, new_version, version_type)
                        st.success("הגרסה נשמרה!")
                        st.rerun()
            else:
                st.error("בדיחה לא נמצאה")
    
    elif mode == "רשימת בדיחות":
        st.header("רשימת בדיחות")
        
        # Filtering options
        filter_status = st.sidebar.selectbox(
            "סינון לפי סטטוס:",
            ["הכל", "ממתין לתרגום", "תורגם"],
            index=0
        )
        
        page_size = st.sidebar.slider("בדיחות בעמוד", 5, 50, 10)
        
        # Filter jokes based on status
        filtered_jokes = []
        for number, joke in manager.jokes.items():
            # Skip deleted jokes
            if joke.get("status") == "deleted":
                continue
                
            if filter_status == "הכל" or \
               (filter_status == "ממתין לתרגום" and joke.get("status") == "pending") or \
               (filter_status == "תורגם" and joke.get("status") == "completed"):
                filtered_jokes.append((number, joke))
        
        # Sort by joke number
        filtered_jokes.sort(key=lambda x: int(x[0]))
        
        # Pagination
        total_pages = len(filtered_jokes) // page_size + (1 if len(filtered_jokes) % page_size else 0)
        page = st.sidebar.number_input("עמוד", min_value=1, max_value=total_pages, value=1)
        start_idx = (page - 1) * page_size
        end_idx = min(start_idx + page_size, len(filtered_jokes))
        
        # Display stats
        st.sidebar.write(f"סה״כ נמצאו: {len(filtered_jokes)} בדיחות")
        st.sidebar.write(f"מוצג עמוד {page} מתוך {total_pages}")
        
        # Display jokes
        for number, joke in filtered_jokes[start_idx:end_idx]:
            with st.expander(f"בדיחה מספר {number} - {joke.get('status', 'pending')}"):
                display_joke_side_by_side(joke, number, manager)
    
    elif mode == "סל מחזור":
        st.header("סל מחזור")
        
        deleted_jokes = manager.get_deleted_jokes()
        if not deleted_jokes:
            st.info("אין בדיחות מחוקות")
            return
            
        st.write(f"נמצאו {len(deleted_jokes)} בדיחות מחוקות:")
        
        # Group restore button
        if st.button("שחזר את כל הבדיחות"):
            restored_count = 0
            for number, _ in deleted_jokes:
                if manager.restore_joke(number):
                    restored_count += 1
            st.success(f"שוחזרו {restored_count} בדיחות")
            st.rerun()
        
        # Display deleted jokes
        for number, joke in deleted_jokes:
            with st.expander(f"בדיחה מספר {number}"):
                col1, col2, col3 = st.columns([6, 6, 1])
                
                with col1:
                    st.markdown("**גרסה מקורית**")
                    st.markdown("~~" + joke["original"] + "~~")
                
                with col2:
                    if joke.get("versions"):
                        st.markdown("**תרגום אחרון**")
                        last_version = joke["versions"][-1]
                        st.markdown("~~" + last_version["text"] + "~~")
                
                with col3:
                    if st.button("שחזר", key=f"restore_{number}"):
                        if manager.restore_joke(number):
                            st.success("הבדיחה שוחזרה")
                            st.rerun()
    
    elif mode == "בדיחות מובילות":
        st.header("בדיחות מובילות")
        
        # Get top jokes excluding deleted ones
        top_jokes = [(num, joke) for num, joke in manager.get_top_jokes(10) 
                    if joke.get("status") != "deleted"]
        
        if not top_jokes:
            st.info("אין עדיין בדיחות מדורגות")
            return
        
        # Display top jokes
        for i, (number, joke) in enumerate(top_jokes, 1):
            with st.expander(f"#{i} - בדיחה מספר {number} (דירוג: {joke.get('rating', 0)})"):
                display_joke_side_by_side(joke, number, manager)
    
    # ... (rest of the existing view modes remain the same)

if __name__ == "__main__":
    main() 