import os
import logging
import time
import pandas as pd
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("8740259120:AAEeHL6gr55wMZxsbxQxVsi1VY5z-Ywsefs")

# 🛡️ ADMINLAR RO'YXATI (O'z Telegram ID raqamingizni yozing)
ADMINS = [
    "5628749214,  # <-- O'z ID raqamingiz
]

logging.basicConfig(level=logging.INFO)
bot = Bot(token="8740259120:AAEeHL6gr55wMZxsbxQxVsi1VY5z-Ywsefs")
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# --- BAZALAR ---
VIDEOS_DB = {}          # {"Mavzu nomi": "file_id"}
TESTS_DB = {}           # {"TEST_KOD": {"answers": ["A", "B", ...], "time_limit": daqiqa}}
ATTENDANCE_CODES = {}   # {"DARS_KOD": True}
USERS_DB = {}           # {user_id: {"name": "...", "coins": 0, "streak": 0, "last_lesson": None, "results": []}}

# --- FSM HOLATLARI ---
class AdminStates(StatesGroup):
    video_topic = State()
    video_file = State()
    
    test_code = State()
    test_time = State()
    test_answers = State()
    
    attendance_code = State()

class StudentStates(StatesGroup):
    solving_test_code = State()
    solving_test_answers = State()
    entering_attendance = State()

# --- ASOSIY MENYU ---
def get_main_menu(user_id):
    kb = [
        [KeyboardButton(text="📚 Video darslar"), KeyboardButton(text="📝 Test ishlash")],
        [KeyboardButton(text="📅 Davomat"), KeyboardButton(text="📊 Mening natijalarim")],
        [KeyboardButton(text="🏆 Reyting")]
    ]
    if user_id in ADMINS:
        kb.append([KeyboardButton(text="⚙️ Admin Panel")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# --- START ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    if user_id not in USERS_DB:
        USERS_DB[user_id] = {"name": message.from_user.full_name, "coins": 0, "streak": 0, "last_lesson": None, "results": []}
    
    await message.answer(
        f"Assalomu alaykum, {message.from_user.full_name}!\n"
        f"SMATH AKADEMIYASI o'quv botiga xush kelibsiz. Kerakli bo'limni tanlang:",
        reply_markup=get_main_menu(user_id)
    )

# ==================== 1. VIDEO DARSLAR ====================
@dp.message(F.text == "📚 Video darslar")
async def show_videos(message: types.Message):
    if not VIDEOS_DB:
        await message.answer("Hozircha video darslar yuklanmagan.")
        return
    
    text = "📚 **Mavjud video darslar ro'yxati:**\n\n"
    for topic in VIDEOS_DB.keys():
        text += f"🔹 {topic}\n"
    text += "\nKo'rish uchun yuqoridagi mavzu nomini yozib yuboring."
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text.in_(VIDEOS_DB.keys()))
async def send_video_lesson(message: types.Message):
    file_id = VIDEOS_DB[message.text]
    await message.answer_video(file_id, caption=f"🎬 Mavzu: {message.text}")


# ==================== 2. DAVOMAT VA STREAK ====================
@dp.message(F.text == "📅 Davomat")
async def attendance_menu(message: types.Message, state: FSMContext):
    await message.answer("🔑 Ustoz bergan dars kodini kiriting (Masalan: `DARS1`):")
    await state.set_state(StudentStates.entering_attendance)

@dp.message(StudentStates.entering_attendance)
async def process_attendance(message: types.Message, state: FSMContext):
    code = message.text.strip().upper()
    user_id = message.from_user.id
    
    if code not in ATTENDANCE_CODES or not ATTENDANCE_CODES[code]:
        await message.answer("❌ Noto'g'ri yoki faol bo'lmagan dars kodi!")
        await state.clear()
        return
    
    user_info = USERS_DB[user_id]
    if user_info.get("last_lesson") == code:
        await message.answer("⚠️ Siz bu dars uchun davomatni allaqachon bergansiz!")
        await state.clear()
        return
    
    user_info["streak"] += 1
    earned_coins = user_info["streak"]
    user_info["coins"] += earned_coins
    user_info["last_lesson"] = code
    
    await state.clear()
    await message.answer(
        f"✅ Davomat tasdiqlandi!\n"
        f"🔥 Muntazamlik darajangiz: {user_info['streak']}-bosqich\n"
        f"🪙 Sizga {earned_coins} ta tanga qo'shildi! Jami tangalar: {user_info['coins']} ta"
    )


# ==================== 3. VAQTLI TEST ISHLASH ====================
@dp.message(F.text == "📝 Test ishlash")
async def start_test_process(message: types.Message, state: FSMContext):
    if not TESTS_DB:
        await message.answer("Hozircha faol testlar mavjud emas.")
        return
    await message.answer("🔑 Test kodini kiriting:")
    await state.set_state(StudentStates.solving_test_code)

@dp.message(StudentStates.solving_test_code)
async def check_test_code(message: types.Message, state: FSMContext):
    code = message.text.strip().upper()
    if code not in TESTS_DB:
        await message.answer("❌ Bunday test topilmadi. Qaytadan urinib ko'ring:")
        return
    
    test_data = TESTS_DB[code]
    expire_time = time.time() + (test_data["time_limit"] * 60)
    total_q = len(test_data["answers"])
    
    await state.update_data(test_code=code, expire_time=expire_time)
    await message.answer(
        f"⏳ Test boshlandi!\n"
        f"📌 Savollar soni: {total_q} ta\n"
        f"⏱ Vaqt: {test_data['time_limit']} daqiqa.\n\n"
        f"Javoblaringizni ketma-ketlikda yuboring (Masalan: `abcdab`):"
    )
    await state.set_state(StudentStates.solving_test_answers)

@dp.message(StudentStates.solving_test_answers)
async def submit_test_answers(message: types.Message, state: FSMContext):
    data = await state.get_data()
    code = data["test_code"]
    expire_time = data["expire_time"]
    
    if time.time() > expire_time:
        await state.clear()
        await message.answer("⏰ Afsuski, test uchun ajratilgan vaqt tugadi!")
        return
    
    user_answers = list(message.text.replace(",", "").replace(" ", "").strip().upper())
    correct_answers = TESTS_DB[code]["answers"]
    
    if len(user_answers) != len(correct_answers):
        await message.answer(f"❌ Xatolik! Savollar soni {len(correct_answers)} ta bo'lishi kerak. Qaytadan kiriting:")
        return
    
    score = sum(1 for u, c in zip(user_answers, correct_answers) if u == c)
    total = len(correct_answers)
    
    user_id = message.from_user.id
    USERS_DB[user_id]["coins"] += score
    USERS_DB[user_id]["results"].append({"test_code": code, "score": score, "total": total})
    
    await state.clear()
    await message.answer(
        f"📊 **Test yakunlandi!**\n"
        f"✅ To'g'ri javoblar: {score}/{total}\n"
        f"🪙 Tangalar: +{score} ta qo'shildi!"
    )
    
    for adm in ADMINS:
        try:
            await bot.send_message(adm, f"🔔 O'quvchi {message.from_user.full_name} `{code}` testini yechdi: {score}/{total}")
        except:
            pass


# ==================== 4. NATIJALARIM & REYTING ====================
@dp.message(F.text == "📊 Mening natijalarim")
async def my_results(message: types.Message):
    user_id = message.from_user.id
    user_info = USERS_DB.get(user_id, {"coins": 0, "results": []})
    
    text = f"📊 **Sizning natijalaringiz:**\n\n🪙 Jami tangalaringiz: {user_info['coins']} ta\n\n"
    if not user_info["results"]:
        text += "Hozircha testlar yechmagansiz."
    else:
        for i, res in enumerate(user_info["results"], 1):
            text += f"{i}. Test: {res['test_code']} | Natija: {res['score']}/{res['total']}\n"
    
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "🏆 Reyting")
async def leaderboard(message: types.Message):
    if not USERS_DB:
        await message.answer("Reyting bo'sh.")
        return
    
    sorted_users = sorted(USERS_DB.values(), key=lambda x: x["coins"], reverse=True)
    text = "🏆 **SMATH AKADEMIYASI REYTINGI** 🏆\n\n"
    for i, user in enumerate(sorted_users[:10], 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        text += f"{medal} {user['name']} — 🪙 {user['coins']} tanga\n"
    
    await message.answer(text)


# ==================== 5. ADMIN PANEL ====================
@dp.message(F.text == "⚙️ Admin Panel")
async def admin_panel(message: types.Message):
    if message.from_user.id not in ADMINS:
        return
    
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Video dars qo'shish"), KeyboardButton(text="➕ Test qo'shish")],
        [KeyboardButton(text="➕ Davomat kodi ochish"), KeyboardButton(text="📊 Excel Natijalar")],
        [KeyboardButton(text="🔙 Asosiy menyu")]
    ], resize_keyboard=True)
    await message.answer("⚙️ Admin panelga xush kelibsiz:", reply_markup=kb)

@dp.message(F.text == "🔙 Asosiy menyu")
async def back_main(message: types.Message):
    await message.answer("Asosiy menyu:", reply_markup=get_main_menu(message.from_user.id))

# Admin: Video dars qo'shish
@dp.message(F.text == "➕ Video dars qo'shish")
async def admin_add_video(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMINS: return
    await message.answer("Mavzu nomini kiriting (masalan: `1-mavzu: Natural sonlar`):")
    await state.set_state(AdminStates.video_topic)

@dp.message(AdminStates.video_topic)
async def admin_video_topic(message: types.Message, state: FSMContext):
    await state.update_data(topic=message.text)
    await message.answer("Endi video faylni yuboring:")
    await state.set_state(AdminStates.video_file)

@dp.message(AdminStates.video_file, F.video)
async def admin_video_save(message: types.Message, state: FSMContext):
    data = await state.get_data()
    VIDEOS_DB[data["topic"]] = message.video.file_id
    await state.clear()
    await message.answer(f"✅ '{data['topic']}' video darsi saqlandi!")

# Admin: Test qo'shish (Faqat to'g'ri javoblar ketma-ketligi)
@dp.message(F.text == "➕ Test qo'shish")
async def admin_add_test(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMINS: return
    await message.answer("Test uchun unikal kod kiriting (masalan: `MATH1`):")
    await state.set_state(AdminStates.test_code)

@dp.message(AdminStates.test_code)
async def admin_test_code(message: types.Message, state: FSMContext):
    await state.update_data(code=message.text.strip().upper())
    await message.answer("Test uchun necha daqiqa vaqt beriladi? (Faqat raqam yozing, masalan: `15`):")
    await state.set_state(AdminStates.test_time)

@dp.message(AdminStates.test_time)
async def admin_test_time(message: types.Message, state: FSMContext):
    try:
        t = int(message.text.strip())
    except:
        await message.answer("Faqat raqam kiriting:")
        return
    await state.update_data(time=t)
    await message.answer("Faqat to'g'ri javoblarni qator qilib kiriting (Masalan: `abcdabcdab`):")
    await state.set_state(AdminStates.test_answers)

@dp.message(AdminStates.test_answers)
async def admin_test_save(message: types.Message, state: FSMContext):
    data = await state.get_data()
    code = data["code"]
    answers = list(message.text.replace(",", "").replace(" ", "").strip().upper())
    
    TESTS_DB[code] = {"answers": answers, "time_limit": data["time"]}
    await state.clear()
    await message.answer(f"✅ `{code}` testi ({len(answers)} ta savol, {data['time']} daqiqa) muvaffaqiyatli saqlandi!")

# Admin: Davomat kodi ochish
@dp.message(F.text == "➕ Davomat kodi ochish")
async def admin_add_attendance(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMINS: return
    await message.answer("Davomat uchun dars kodini kiriting (masalan: `DARS1`):")
    await state.set_state(AdminStates.attendance_code)

@dp.message(AdminStates.attendance_code)
async def admin_attendance_save(message: types.Message, state: FSMContext):
    code = message.text.strip().upper()
    ATTENDANCE_CODES[code] = True
    await state.clear()
    await message.answer(f"✅ `{code}` dars kodi faollashtirildi!")

# Admin: Excel natijalar
@dp.message(F.text == "📊 Excel Natijalar")
async def admin_excel_results(message: types.Message):
    if message.from_user.id not in ADMINS: return
    if not USERS_DB:
        await message.answer("Hozircha ma'lumotlar yo'q.")
        return
    
    report = []
    for uid, info in USERS_DB.items():
        report.append({
            "Telegram ID": uid,
            "Ismi": info["name"],
            "Tangalar": info["coins"],
            "Muntazamlik (Streak)": info["streak"],
            "Yechilgan testlar soni": len(info["results"])
        })
    
    df = pd.DataFrame(report)
    file_path = "smath_report.xlsx"
    df.to_excel(file_path, index=False)
    
    from aiogram.types import FSInputFile
    await message.answer_document(FSInputFile(file_path), caption="📊 O'quvchilarning umumiy hisoboti:")
    if os.path.exists(file_path):
        os.remove(file_path)

async def main():
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())