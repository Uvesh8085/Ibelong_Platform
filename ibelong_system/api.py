import frappe
import json
import google.generativeai as genai

def setup_gemini():
    api_key = frappe.conf.get("gemini_api_key")
    if not api_key: return None
    genai.configure(api_key=api_key)
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods and 'gemini' in m.name:
            return genai.GenerativeModel(m.name)
    return None

def get_schema(doctype):
    if not doctype: return ""
    meta = frappe.get_meta(doctype)
    return ", ".join([f.fieldname for f in meta.fields if f.fieldtype not in ['Section Break', 'Column Break', 'HTML']])

@frappe.whitelist()
def ask_copilot_chat(user_message, doctype=None):
    try:
        if not user_message: return "I didn't quite catch that."
        model = setup_gemini()
        if not model: return "System Error: Gemini API key missing."
        
        available_fields = get_schema(doctype)
        
        # Safe string concatenation (No triple quotes)
        prompt = "You are an AI embedded in Frappe.\n"
        prompt += "DocType: " + str(doctype) + "\n"
        prompt += "Fields: " + str(available_fields) + "\n"
        prompt += "Answer clearly.\nUser message: " + str(user_message)
        
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "Quota" in error_msg or "ResourceExhausted" in error_msg:
            return "Whoa there! 🚦 Google's free tier speed limit was reached. Wait 15 seconds."
        return "Oops! Backend crashed. Error: " + error_msg

@frappe.whitelist()
def ask_copilot_agent(user_message, doctype=None):
    try:
        if not user_message: return {"action": "message", "payload": "I didn't quite catch that."}
        model = setup_gemini()
        if not model: return {"action": "message", "payload": "System Error: Gemini API key missing."}
        
        available_fields = get_schema(doctype)
        
        # Safe string concatenation (No triple quotes)
        prompt = "You are an AI Agent. DocType: " + str(doctype) + "\n"
        prompt += "Fields: " + str(available_fields) + "\n"
        prompt += "Reply ONLY in JSON format.\n"
        prompt += "If filtering data, return:\n"
        prompt += "{\"action\": \"filter\", \"payload\": [[\"field_name\", \"=\", \"value\"]]}\n"
        prompt += "If answering a question, return:\n"
        prompt += "{\"action\": \"message\", \"payload\": \"Your answer here\"}\n"
        prompt += "User message: " + str(user_message)
        
        response = model.generate_content(prompt)
        
        # THE FIX: Extract JSON using brackets instead of backticks
        text = response.text
        start_idx = text.find('{')
        end_idx = text.rfind('}')
        
        if start_idx != -1 and end_idx != -1:
            clean_json = text[start_idx:end_idx+1]
            return json.loads(clean_json)
        else:
            return {"action": "message", "payload": "Error: AI did not return a valid command."}
            
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "Quota" in error_msg or "ResourceExhausted" in error_msg:
            return {"action": "message", "payload": "Whoa there! 🚦 Google's speed limit was reached. Wait 15 seconds."}
        return {"action": "message", "payload": "Backend Error: " + error_msg}