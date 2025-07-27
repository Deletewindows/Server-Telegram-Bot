import os
import json
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
import random
import asyncio
from datetime import datetime, timedelta

# Инициализация бота (без прокси)
bot = Bot(token='8084621912:AAG0zWp3tEn4voc6IyxoevvH96eUhVtVlxw')
dp = Dispatcher(storage=MemoryStorage())
DATA_FILE = 'user_data.json'
DAILY_GAME_LIMIT = 50
BOT_USERNAME = 'GiftBox_tgbot'

# Загрузка данных
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        user_data = json.load(f)
else:
    user_data = {}

class User:
    def __init__(self, user_id):
        self.user_id = str(user_id)
        self.stars = 0.0
        self.last_click_time = None
        self.sponsors_checked = False
        self.referrals = []
        self.referrer = None
        self.games_played_today = 0
        self.last_game_date = None
        
    def to_dict(self):
        return {
            'stars': self.stars,
            'last_click_time': self.last_click_time.isoformat() if self.last_click_time else None,
            'sponsors_checked': self.sponsors_checked,
            'referrals': self.referrals,
            'referrer': self.referrer,
            'games_played_today': self.games_played_today,
            'last_game_date': self.last_game_date.isoformat() if self.last_game_date else None
        }
    
    @classmethod
    def from_dict(cls, user_id, data):
        user = cls(user_id)
        user.stars = data.get('stars', 0.0)
        if data.get('last_click_time'):
            user.last_click_time = datetime.fromisoformat(data['last_click_time'])
        user.sponsors_checked = data.get('sponsors_checked', False)
        user.referrals = data.get('referrals', [])
        user.referrer = data.get('referrer')
        user.games_played_today = data.get('games_played_today', 0)
        if data.get('last_game_date'):
            user.last_game_date = datetime.fromisoformat(data['last_game_date'])
        return user
    
    def reset_daily_limit_if_needed(self):
        today = datetime.now().date()
        if self.last_game_date and self.last_game_date.date() != today:
            self.games_played_today = 0
            self.last_game_date = datetime.now()
            return True
        return False

def save_data():
    data_to_save = {uid: u.to_dict() if isinstance(u, User) else u for uid, u in user_data.items()}
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data_to_save, f, ensure_ascii=False, indent=2)

def get_user(user_id):
    user_id = str(user_id)
    if user_id not in user_data:
        user_data[user_id] = User(user_id)
    elif isinstance(user_data[user_id], dict):
        user_data[user_id] = User.from_dict(user_id, user_data[user_id])
    return user_data[user_id]

def get_main_keyboard(user_id):
    user = get_user(user_id)
    user.reset_daily_limit_if_needed()
    
    buttons = [
        [InlineKeyboardButton(text="⭐ Заработать (+1⭐)", callback_data="earn_stars")],
        [InlineKeyboardButton(text="🎮 Игры", callback_data="play_games")],
        [InlineKeyboardButton(text=f"🌟 Баланс: {user.stars:.2f}⭐", callback_data="show_stars")],
        [InlineKeyboardButton(text="👥 Рефералы (+3⭐)", callback_data="show_referrals")],
    ]
    
    if not user.sponsors_checked:
        buttons.append([InlineKeyboardButton(text="✅ Проверить спонсоров", callback_data="check_sponsors")])
    
    buttons.extend([
        [InlineKeyboardButton(text="📰 Новости", url="https://t.me/GiftBoxNews")],
        [InlineKeyboardButton(text="📄 Соглашение", url="https://t.me/useragreement_GiftBox")]
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_games_keyboard(user_id):
    user = get_user(user_id)
    user.reset_daily_limit_if_needed()
    remaining = DAILY_GAME_LIMIT - user.games_played_today
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🎰 Слоты (10⭐) | Осталось: {remaining}/{DAILY_GAME_LIMIT}", callback_data="slots")],
        [InlineKeyboardButton(text=f"🎯 Дартс (15⭐) | Осталось: {remaining}/{DAILY_GAME_LIMIT}", callback_data="darts")],
        [InlineKeyboardButton(text=f"🎲 Кубик (5⭐) | Осталось: {remaining}/{DAILY_GAME_LIMIT}", callback_data="dice")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])

def get_sponsors_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1⃣ Спонсор 1", url="https://t.me/starsy_zarabotox_bot?start=8318454113")],
        [InlineKeyboardButton(text="2⃣ Спонсор 2", url="http://t.me/StarsovEarnBot?start=ycntHR20E")],
        [InlineKeyboardButton(text="3⃣ Спонсор 3", url="https://t.me/GoGift_official_bot?startapp=undefined")],
        [InlineKeyboardButton(text="4⃣ Спонсор 4", url="https://t.me/GiftsBattle_bot?startapp=ref_Vp7GrD1ZV")],
        [InlineKeyboardButton(text="5⃣ Спонсор 5", url="https://t.me/GiftBoxNews")],
        [InlineKeyboardButton(text="✅ Я подписался", callback_data="verify_sponsors")]
    ])

def get_referral_link(user_id):
    return f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"

async def check_game_limit(user_id):
    user = get_user(user_id)
    user.reset_daily_limit_if_needed()
    if user.games_played_today >= DAILY_GAME_LIMIT:
        return False, f"⚠️ Лимит игр исчерпан ({DAILY_GAME_LIMIT}/день)"
    return True, ""

async def play_game(user_id, game_name, cost, win_table):
    user = get_user(user_id)
    ok, msg = await check_game_limit(user_id)
    if not ok: return msg
    
    if user.stars < cost:
        return f"❌ Не хватает звёзд! Нужно {cost}⭐"
    
    user.stars -= cost
    user.games_played_today += 1
    user.last_game_date = datetime.now()
    
    result = random.choices(
        list(win_table.keys()),
        weights=[w[0] for w in win_table.values()],
        k=1
    )[0]
    
    win = random.randint(*win_table[result][1])
    user.stars += win
    
    save_data()
    return (
        f"{result}\n"
        f"💸 Ставка: {cost}⭐\n"
        f"🏆 Выигрыш: {win}⭐\n"
        f"🌟 Баланс: {user.stars:.2f}⭐\n"
        f"🎮 Игр сегодня: {user.games_played_today}/{DAILY_GAME_LIMIT}"
    )

@dp.message(Command("start"))
async def start(message: types.Message):
    args = message.text.split()
    user = get_user(message.from_user.id)
    
    # Реферальная система
    if len(args) > 1 and args[1].startswith('ref_'):
        referrer_id = args[1][4:]
        if referrer_id != user.user_id and referrer_id in user_data:
            if not user.referrer:  # Проверяем, что у пользователя еще нет реферера
                user.referrer = referrer_id
                referrer = get_user(referrer_id)
                if user.user_id not in referrer.referrals:
                    referrer.referrals.append(user.user_id)
                    referrer.stars += 3.0
                    await bot.send_message(
                        referrer_id,
                        f"🎉 <b>Новый реферал!</b>\n"
                        f"👤 ID: <code>{user.user_id}</code>\n"
                        f"💰 Получено: <b>+3⭐</b>\n"
                        f"👥 Всего: <b>{len(referrer.referrals)}</b>\n\n"
                        f"🌟 Ваш баланс: <b>{referrer.stars:.2f}⭐</b>",
                        parse_mode="HTML"
                    )
                    save_data()
    
    welcome_msg = (
        f"🎁 <b>Добро пожаловать, {message.from_user.first_name}!</b>\n\n"
        f"🌟 <b>Ваш баланс:</b> {user.stars:.2f}⭐\n\n"
        f"💎 <i>Зарабатывайте звёзды и обменивайте их на призы!</i>"
    )
    
    await message.answer(
        welcome_msg,
        reply_markup=get_main_keyboard(user.user_id),
        parse_mode="HTML"
    )
    save_data()

@dp.callback_query(F.data == "earn_stars")
async def earn_stars(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id)
    now = datetime.now()
    
    if user.last_click_time and (now - user.last_click_time) < timedelta(minutes=5):
        wait = 5 - (now - user.last_click_time).seconds // 60
        await callback.answer(f"⏳ Подождите {wait} минут", show_alert=True)
        return
    
    user.stars += 1.0
    user.last_click_time = now
    
    await callback.answer(
        f"⭐ +1 звезда!\n"
        f"🌟 Баланс: {user.stars:.2f}⭐\n"
        f"⏳ Следующее через 5 мин",
        show_alert=True
    )
    await callback.message.edit_reply_markup(reply_markup=get_main_keyboard(user.user_id))
    save_data()

@dp.callback_query(F.data == "show_referrals")
async def show_referrals(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id)
    ref_count = len(user.referrals)
    earned = ref_count * 3
    ref_link = get_referral_link(user.user_id)
    
    message_text = (
        f"👥 <b>Ваша реферальная программа</b>\n\n"
        f"🔗 <b>Ваша ссылка:</b>\n<code>{ref_link}</code>\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"• Приглашено: <b>{ref_count} чел</b>\n"
        f"• Заработано: <b>{earned}⭐</b>\n\n"
        f"💡 <i>Каждый приглашенный друг приносит вам +3⭐</i>"
    )
    
    share_button = InlineKeyboardButton(
        text="📤 Поделиться ссылкой", 
        url=f"https://t.me/share/url?url={ref_link}&text=Присоединяйся%20к%20GiftBox%20и%20зарабатывай%20звёзды!"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[share_button]])
    
    await callback.message.edit_text(
        message_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "slots")
async def play_slots(callback: types.CallbackQuery):
    slots_win_table = {
        "🍒🍒🍒": [5, (40, 50)],
        "🍇🍇🍇": [10, (20, 30)],
        "🔔🔔🔔": [15, (10, 20)],
        "Проигрыш": [70, (0, 0)]
    }
    result = await play_game(callback.from_user.id, "Слоты", 10, slots_win_table)
    await callback.message.edit_text(result, reply_markup=get_games_keyboard(callback.from_user.id))
    await callback.answer()

@dp.callback_query(F.data == "darts")
async def play_darts(callback: types.CallbackQuery):
    darts_win_table = {
        "🎯 В яблочко!": [10, (60, 75)],
        "👍 Хороший бросок": [25, (20, 30)],
        "😐 Почти попал": [30, (10, 15)],
        "😢 Мимо": [35, (0, 0)]
    }
    result = await play_game(callback.from_user.id, "Дартс", 15, darts_win_table)
    await callback.message.edit_text(result, reply_markup=get_games_keyboard(callback.from_user.id))
    await callback.answer()

@dp.callback_query(F.data == "dice")
async def play_dice(callback: types.CallbackQuery):
    dice_win_table = {
        "🎯 Шестёрка!": [15, (20, 25)],
        "👍 Пятёрка": [25, (8, 12)],
        "😐 Четвёрка": [30, (5, 8)],
        "😢 Меньше 4": [30, (0, 0)]
    }
    result = await play_game(callback.from_user.id, "Кубик", 5, dice_win_table)
    await callback.message.edit_text(result, reply_markup=get_games_keyboard(callback.from_user.id))
    await callback.answer()

@dp.callback_query(F.data == "check_sponsors")
async def check_sponsors(callback: types.CallbackQuery):
    sponsors_message = (
        "📢 <b>Подпишитесь на всех спонсоров:</b>\n\n"
        "1⃣ [Спонсор 1](https://t.me/starsy_zarabotox_bot?start=8318454113)\n"
        "2⃣ [Спонсор 2](http://t.me/StarsovEarnBot?start=ycntHR20E)\n"
        "3⃣ [Спонсор 3](https://t.me/GoGift_official_bot?startapp=undefined)\n"
        "4⃣ [Спонсор 4](https://t.me/GiftsBattle_bot?startapp=ref_Vp7GrD1ZV)\n"
        "5⃣ [Спонсор 5](https://t.me/GiftBoxNews)\n\n"
        "<i>После подписки нажмите кнопку ниже</i>"
    )
    await callback.message.answer(
        sponsors_message,
        reply_markup=get_sponsors_keyboard(),
        disable_web_page_preview=True,
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "verify_sponsors")
async def verify_sponsors(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id)
    user.sponsors_checked = True
    await callback.message.answer(
        "✅ <b>Проверено!</b> Теперь вы можете играть в игры",
        reply_markup=get_main_keyboard(callback.from_user.id),
        parse_mode="HTML"
    )
    save_data()
    await callback.answer()

@dp.callback_query(F.data == "play_games")
async def play_games_menu(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id)
    if not user.sponsors_checked:
        await callback.answer("❌ Сначала проверьте спонсоров!", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🎮 <b>Выберите игру:</b>",
        reply_markup=get_games_keyboard(callback.from_user.id),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "🔙 <b>Главное меню</b>",
        reply_markup=get_main_keyboard(callback.from_user.id),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "show_stars")
async def show_stars(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id)
    await callback.answer(f"🌟 Ваш баланс: {user.stars:.2f}⭐", show_alert=True)

async def main():
    try:
        print("🟢 Бот запускается...")
        await dp.start_polling(bot)
    except Exception as e:
        print(f"🔴 Ошибка: {e}")
        print("\nСоветы по исправлению:")
        print("1. Проверьте интернет-соединение")
        print("2. Убедитесь, что токен бота верный")
        print("3. Если Telegram заблокирован - используйте VPN")
        print("4. Попробуйте перезапустить Pydroid 3")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        save_data()