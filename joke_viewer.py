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
                raw_jokes = json.load(f)
                # Check if jokes are in the new format or need conversion
                self.jokes = {}
                for number, content in raw_jokes.items():
                    if isinstance(content, str):
                        # Convert from old format
                        self.jokes[number] = {
                            "original": content,
                            "versions": [],
                            "status": "pending"
                        }
                    else:
                        # Already in new format
                        self.jokes[number] = content
        except FileNotFoundError:
            self.jokes = {}
            
    def save_jokes(self):
        with open(self.jokes_file, 'w', encoding='utf-8') as f:
            json.dump(self.jokes, f, ensure_ascii=False, indent=2)
            
    def get_joke_versions(self, number: str) -> Dict:
        """Get all versions of a specific joke"""
        if number not in self.jokes:
            self.jokes[number] = {
                "original": "",
                "versions": [],
                "status": "pending"
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
    # Add action buttons above the joke
    col_edit, col_delete = st.columns(2)
    
    with col_edit:
        if st.button("ערוך", key=f"edit_{number}"):
            st.session_state[f"editing_{number}"] = True
    
    with col_delete:
        if joke_data.get("status") != "deleted":
            if st.button("מחק", key=f"delete_{number}"):
                if st.session_state.get(f"confirm_delete_{number}", False):
                    manager.mark_as_deleted(number)
                    st.success("הבדיחה סומנה כמחוקה")
                    st.rerun()
                else:
                    st.session_state[f"confirm_delete_{number}"] = True
                    st.warning("לחץ שוב למחיקה")
        else:
            st.info("בדיחה מחוקה")
    
    # Show edit form if editing
    if st.session_state.get(f"editing_{number}", False):
        with st.form(key=f"edit_form_{number}"):
            edited_text = st.text_area("ערוך את הבדיחה:", value=joke_data["original"])
            edit_type = st.text_input("סוג העריכה:", value="edited")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.form_submit_button("שמור"):
                    manager.edit_joke(number, edited_text, edit_type)
                    st.session_state[f"editing_{number}"] = False
                    st.success("העריכה נשמרה")
                    st.rerun()
            with col2:
                if st.form_submit_button("בטל"):
                    st.session_state[f"editing_{number}"] = False
                    st.rerun()
    
    # Display joke content
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**גרסה מקורית**")
        if joke_data.get("status") == "deleted":
            st.markdown("~~" + joke_data["original"] + "~~")
        else:
            st.write(joke_data["original"])
    
    with col2:
        st.markdown("**תרגום**")
        if joke_data.get("versions"):
            if len(joke_data["versions"]) > 1:
                version_index = st.selectbox(
                    "בחר גרסה:",
                    range(len(joke_data["versions"])),
                    format_func=lambda i: f'גרסה {i+1} - {joke_data["versions"][i]["type"]} ({joke_data["versions"][i]["timestamp"]})'
                )
                selected_version = joke_data["versions"][version_index]
            else:
                selected_version = joke_data["versions"][0]
            
            if joke_data.get("status") == "deleted":
                st.markdown("~~" + selected_version["text"] + "~~")
            else:
                st.write(selected_version["text"])
        else:
            st.info("טרם נוצר תרגום")

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
        ["חיפוש בדיחות", "בדיחה לפי מספר", "רשימת בדיחות", "ניהול תרגומים"]
    )
    
    if mode == "חיפוש בדיחות":
        st.header("חיפוש בדיחות")
        query = st.text_input("הכנס מילות חיפוש:")
        
        if query:
            # Search in both original and translated versions
            results = []
            for number, joke_data in manager.jokes.items():
                # Search in original
                if query.lower() in joke_data["original"].lower():
                    results.append((number, joke_data))
                    continue
                    
                # Search in versions
                for version in joke_data["versions"]:
                    if query.lower() in version["text"].lower():
                        results.append((number, joke_data))
                        break
            
            if results:
                st.write(f"נמצאו {len(results)} תוצאות:")
                for num, joke_data in results:
                    with st.expander(f"בדיחה מספר {num}"):
                        display_joke_side_by_side(joke_data, num, manager)
            else:
                st.warning("לא נמצאו תוצאות")
    
    elif mode == "ניהול תרגומים":
        st.header("ניהול תרגומים")
        
        # Translation settings
        with st.expander("הגדרות תרגום"):
            model = create_gemini_model()
            if not model:
                st.error("לא נמצא API key של Gemini ב-secrets.toml")
                return
                
            prompt_template = st.text_area(
                "תבנית פרומפט:",
                create_translation_prompt("{{joke_text}}"),
                height=300
            )
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
                    prompt = prompt_template.replace("{{joke_text}}", joke["original"])
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
    
    # ... (rest of the existing view modes remain the same)

if __name__ == "__main__":
    main() 