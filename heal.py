import os
import json
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters
)
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# ====== ENV SETUP ======
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGCHAIN_API_KEY", "")
os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGCHAIN_PROJECT", "healmate_project")
os.environ["LANGCHAIN_TRACING_V2"] = "true"

# ====== CONVERSATION STATES ======
NAME, AGE, GENDER, SYMPTOMS, AI_SYMPTOMS = range(5)

# ====== SAVE DATA PER USER ======
def save_user_data(user_id, data):
    os.makedirs("users_data", exist_ok=True)
    filename = f"users_data/user_{user_id}.json"
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)

# ====== BASIC SURVEY (RULE-BASED) ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()  # Reset old session
    await update.message.reply_text("👋 Welcome to Healmate!\nWhat is your name?")
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text
    await update.message.reply_text("How old are you?")
    return AGE

async def get_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["age"] = update.message.text
    reply_keyboard = [["Male", "Female", "Other"]]
    await update.message.reply_text(
        "Select your gender:",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
    )
    return GENDER

async def get_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["gender"] = update.message.text
    await update.message.reply_text("Please describe your symptoms (e.g., fever, cough, headache, stomach ache):")
    return SYMPTOMS

async def get_symptoms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    symptoms = update.message.text.lower()
    context.user_data["symptoms"] = symptoms
    user_id = str(update.effective_user.id)

    # Save to user-specific JSON
    save_user_data(user_id, context.user_data)

    # ====== Rule-based advice ======
    if "fever" in symptoms and "cough" in symptoms:
        advice = "🩺 Possible flu. Rest, drink warm fluids, and monitor temperature."
    elif "headache" in symptoms:
        advice = "💊 Likely tension or dehydration. Rest and drink plenty of water."
    elif "stomach ache" in symptoms or "stomach pain" in symptoms:
        advice = "🥣 Could be indigestion. Eat light meals, avoid spicy food, and drink warm water."
    elif "cough" in symptoms and "chest pain" in symptoms:
        advice = "⚠️ Persistent cough with chest pain may indicate infection. Please consult a doctor."
    else:
        advice = "✅ Your information has been recorded. Use /aiadvice for a detailed check."

    await update.message.reply_text(advice)
    return ConversationHandler.END

# ====== AI ADVICE WITH GROQ ======
async def aiadvice_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📝 Please describe your symptoms in detail (duration, severity, other issues):")
    return AI_SYMPTOMS

async def aiadvice_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_symptoms = update.message.text.strip()
    user_id = str(update.effective_user.id)

    await update.message.reply_text("🧠 Analyzing with AI...")

    try:
        # Prompt for Groq LLM
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a rural healthcare assistant. 
            Based on the user's symptoms, give:
            1. Possible Condition
            2. Home Remedies
            3. When to See Doctor
            Keep it short, clear, and under 6 lines.
            Only return the advice, no reasoning."""),
            ("user", user_symptoms)
        ])

        llm = ChatGroq(model="gemma2-9b-it", groq_api_key=GROQ_API_KEY)
        chain = prompt | llm | StrOutputParser()

        result = chain.invoke({})
        await update.message.reply_text(f"🤖 AI Health Advice:\n{result}")

        # Save AI advice alongside user input
        context.user_data["ai_advice"] = result
        save_user_data(user_id, context.user_data)

    except Exception as e:
        await update.message.reply_text(f"❌ Error generating advice: {str(e)}")

    return ConversationHandler.END

# ====== CANCEL ======
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelled. Use /start or /aiadvice to begin again.")
    return ConversationHandler.END

# ====== MAIN ======
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Basic survey
    survey_conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_age)],
            GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_gender)],
            SYMPTOMS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_symptoms)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # AI advice
    aiadvice_conv = ConversationHandler(
        entry_points=[CommandHandler("aiadvice", aiadvice_start)],
        states={
            AI_SYMPTOMS: [MessageHandler(filters.TEXT & ~filters.COMMAND, aiadvice_process)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(survey_conv)
    app.add_handler(aiadvice_conv)
    app.run_polling()

if __name__ == "__main__":
    main()
