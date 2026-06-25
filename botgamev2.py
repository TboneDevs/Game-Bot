import asyncio
import random
import re
import json
import os
import time
from threading import Lock
from telebot.async_telebot import AsyncTeleBot
from telebot import types

# ============ CONFIG ============
BOT_TOKEN = os.getenv("BOT_TOKEN") 
bot = AsyncTeleBot(BOT_TOKEN)

OWNER_ID = 6531314640
EXTRA_ADMIN = 8650959684
ADMINS = [OWNER_ID, EXTRA_ADMIN]

LEADERBOARD_FILE = "leaderboard.json"
INVENTORY_FILE = "inventory.json"
TOKENS_FILE = "claim_tokens.json"
TOURNAMENTS_FILE = "tournaments.json"

admin_inventory = {}
claim_tokens = {}
leaderboard_cache = {}
tournaments = {}
auto_tasks = {}

admin_states = {}
inventory_lock = Lock()
claim_tokens_lock = Lock()

# ============ UTILITIES ============
def safe_load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception:
            return default
    return default

def safe_save_json(path, data):
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error saving {path}: {e}")

def load_inventory():
    return safe_load_json(INVENTORY_FILE, {"CPM2 Regular": [], "CPM2 Coins": [], "CarX Street": []})

def save_inventory(data):
    safe_save_json(INVENTORY_FILE, data)

def load_claim_tokens():
    return safe_load_json(TOKENS_FILE, {})

def save_claim_tokens(data):
    safe_save_json(TOKENS_FILE, data)

def load_leaderboard():
    return safe_load_json(LEADERBOARD_FILE, {})

def save_leaderboard(data):
    safe_save_json(LEADERBOARD_FILE, data)

def add_win_to_leaderboard(username):
    data = load_leaderboard()
    data[username] = data.get(username, 0) + 1
    save_leaderboard(data)

def load_tournaments():
    return safe_load_json(TOURNAMENTS_FILE, {})

def save_tournaments():
    safe_save_json(TOURNAMENTS_FILE, tournaments)

admin_inventory = load_inventory()
claim_tokens = load_claim_tokens()
leaderboard_cache = load_leaderboard()
tournaments = load_tournaments()

def ensure_tournament(chat_id):
    key = str(chat_id)
    if key not in tournaments:
        tournaments[key] = {
            'game': None,
            'prize_cat': None,
            'prize_qty': 0,
            'players': [],
            'eliminated_this_round': [],
            'last_msg_id': None,
            'current_round': 1,
            'answered_users': [],
            'tic_tac_toe_board': None,
            'auto_end_at': None
        }
    return tournaments[key]

def get_tournament(chat_id):
    return ensure_tournament(chat_id)

# ============ HARDCORE QUESTIONS ============
HARDCORE_QUESTIONS = [
    {"q": "12 * 4 - (15 + 7) * 2 / 4", "a": "37"},
    {"q": "Square root of 144 multiplied by 7 minus 15", "a": "69"},
    {"q": "If 3x + 7 = 22, what is the value of 5x - 3?", "a": "22"},
    {"q": "Complete the sequence: 2, 6, 12, 20, 30, ?", "a": "42"},
    {"q": "7 * 8 + (9 - 3) * 4 / 2", "a": "68"},
    {"q": "What is 15% of 200 added to 45?", "a": "75"},
    {"q": "Solve for x: 4x - 12 = 2x + 8", "a": "10"},
    {"q": "Next number in pattern: 1, 4, 9, 16, 25, ?", "a": "36"},
    {"q": "(50 / 2) * 3 - (10 * 5)", "a": "25"},
    {"q": "If a=5, b=10, c=2. What is (a * b) - (b / c)?", "a": "45"},
    {"q": "Cube root of 27 multiplied by (14 - 6)", "a": "24"},
    {"q": "Solve: 100 - 45 / 5 * 3 + 12", "a": "85"},
    {"q": "Next number in pattern: 3, 7, 15, 31, ?", "a": "63"},
    {"q": "If 5 shirts cost $500, how much do 12 shirts cost?", "a": "1200"},
    {"q": "Value of y: 2y + 15 = 45 - y", "a": "10"},
    {"q": "75 minus 3 squared multiplied by 5", "a": "30"},
    {"q": "Complete the pattern: 100, 90, 81, 73, ?", "a": "66"},
    {"q": "(18 * 3) / 2 + (40 - 15)", "a": "52"},
    {"q": "If a triangle has bases of 6 and 8, what is 6 * 8 / 2?", "a": "24"},
    {"q": "Solve: 250 / 5 - 12 * 3", "a": "14"},
    {"q": "What is 20% of 75 multiplied by 2?", "a": "30"},
    {"q": "If 4x = 64, what is x squared?", "a": "256"},
    {"q": "Next number in pattern: 2, 4, 8, 16, 32, ?", "a": "64"},
    {"q": "Solve: (14 + 16) * (25 - 20) / 2", "a": "75"},
    {"q": "What is 11 * 11 minus 21?", "a": "100"},
    {"q": "Solve for x: 5x + 3 = 3x + 19", "a": "8"},
    {"q": "Next number in pattern: 5, 11, 23, 47, ?", "a": "95"},
    {"q": "Value of: (8 * 9) - (6 * 7) + 10", "a": "40"},
    {"q": "What is 120 divided by 4 multiplied by 3?", "a": "90"},
    {"q": "Solve: 45 + 55 - 12 * 5", "a": "40"},
]

# ============ PROGRESS BAR ============
def format_progress_bar(percent, length=12):
    filled = int(round((percent / 100.0) * length))
    empty = max(0, length - filled)
    return "█" * filled + "░" * empty

# ============ AUTO-START TIMER ============
async def schedule_auto_start(chat_id, msg_id, min_minutes=25, max_minutes=35):
    cancel_auto_start(chat_id)
    minutes = random.randint(min_minutes, max_minutes)
    duration_seconds = minutes * 60
    end_ts = int(time.time() + duration_seconds)

    t = get_tournament(chat_id)
    t['auto_end_at'] = end_ts
    t['last_msg_id'] = msg_id
    save_tournaments()

    task = asyncio.create_task(_auto_countdown(chat_id))
    auto_tasks[int(chat_id)] = task

async def _auto_countdown(chat_id):
    try:
        key = str(chat_id)
        if key not in tournaments:
            return
        t = tournaments[key]
        end_ts = t.get('auto_end_at')
        if not end_ts:
            return

        while True:
            now = int(time.time())
            remaining = max(0, end_ts - now)
            max_seconds = 35 * 60
            percent = min(100.0, (1 - remaining / max_seconds) * 100.0) if max_seconds > 0 else 100.0

            minutes_left = remaining // 60
            seconds_left = remaining % 60
            time_left_str = f"{minutes_left}m {seconds_left}s" if minutes_left > 0 else f"{seconds_left}s"

            tournament = get_tournament(chat_id)
            game_name = tournament.get('game', 'Unknown')
            prize_qty = tournament.get('prize_qty', 0)
            prize_cat = tournament.get('prize_cat', 'Unknown')
            players = tournament.get('players', [])
            count = len(players)
            progress = format_progress_bar(percent, length=12)
            
            lobby_text = (
                "◢◤ <b>TNNR TOURNAMENT LOBBY</b> ◢◤\n"
                "──────────────────────────\n"
                f"🎮 <b>GAME:</b> {game_name}\n"
                f"🎁 <b>REWARD:</b> {prize_qty}x {prize_cat} Account(s)\n"
                f"👥 <b>SLOTS:</b> {count} Registered\n"
                "──────────────────────────\n"
                f"⏳ <b>Auto-start in:</b> {time_left_str}\n"
                f"{progress} {percent:.0f}%\n\n"
                "» <i>Click the button below to secure your slot!</i>"
            )
            try:
                await bot.edit_message_text(lobby_text, chat_id, tournament.get('last_msg_id'), parse_mode="HTML",
                                            reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🎮 JOIN BRACKET", callback_data="join_game")))
            except Exception:
                pass

            if remaining <= 0:
                try:
                    await bot.delete_message(chat_id, tournament.get('last_msg_id'))
                except Exception:
                    pass
                tournament.pop('auto_end_at', None)
                save_tournaments()
                auto_tasks.pop(int(chat_id), None)
                try:
                    await bot.send_message(chat_id, "🏁 <b>Round 1 — Game started!</b>", parse_mode="HTML")
                except Exception:
                    pass
                await trigger_next_round(chat_id)
                return

            interval = 5 if remaining <= 60 else 30
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        return
    except Exception as e:
        print("Auto-countdown error for chat", chat_id, ":", e)
        return

def cancel_auto_start(chat_id):
    task = auto_tasks.get(int(chat_id))
    if task:
        try:
            task.cancel()
        except Exception:
            pass
    auto_tasks.pop(int(chat_id), None)
    t = get_tournament(chat_id)
    if 'auto_end_at' in t:
        t.pop('auto_end_at', None)
        save_tournaments()

# ============ COMMANDS ============
@bot.message_handler(commands=['leaderboard'])
async def show_leaderboard(message):
    scores = load_leaderboard()
    if not scores:
        await bot.reply_to(message, "📊 <b>TNNR SCOREBOARD</b>\n\n<i>No winners recorded yet. Start a game to build the board!</i>", parse_mode="HTML")
        return
    sorted_scores = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:10]
    board_text = "🏆 <b>TNNR HALL OF FAME — TOP 10 PLAYERS</b>\n"
    board_text += "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    medals = ["👑", "🥈", "🥉"]
    for index, (player, wins) in enumerate(sorted_scores):
        rank_label = medals[index] if index < 3 else f"<b>#{index + 1}</b>"
        board_text += f"{rank_label} {player} — <b>{wins} Win(s)</b>\n"
    board_text += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    board_text += "⚡ <i>Keep winning tournaments to secure your spot at the top!</i>"
    await bot.send_message(message.chat.id, board_text, parse_mode="HTML")

@bot.message_handler(commands=['addinv'])
async def add_inventory_menu(message):
    if message.from_user.id not in ADMINS:
        return
    if message.chat.type != "private":
        await bot.reply_to(message, "❌ Admin, please use this command in a private chat.", parse_mode="HTML")
        return
    markup = types.InlineKeyboardMarkup()
    markup.row(types.InlineKeyboardButton("🚗 CPM2 Regular (20 Cars)", callback_data="add_CPM2 Regular"))
    markup.row(types.InlineKeyboardButton("💰 CPM2 Coins (12k Coins)", callback_data="add_CPM2 Coins"))
    markup.row(types.InlineKeyboardButton("🏁 CarX Street", callback_data="add_CarX Street"))
    await bot.send_message(message.chat.id, "🎒 <b>INVENTORY RESTOCK MENU</b>\n\nSelect the exact category you want to drop your bulk stock into:", reply_markup=markup, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data.startswith("add_"))
async def handle_add_choice(call):
    if call.from_user.id not in ADMINS:
        return
    category = call.data.replace("add_", "")
    admin_states[call.from_user.id] = category
    await bot.edit_message_text(f"📥 <b>Category Selected: {category}</b>\n\nPlease <b>COPY-PASTE</b> your list of accounts now (One account per line).\n\nExample:\n<code>user1@gmail.com:pass1</code>\n<code>user2@gmail.com:pass2</code>", call.message.chat.id, call.message.message_id, parse_mode="HTML")

@bot.message_handler(func=lambda message: message.from_user.id in admin_states and message.chat.type == "private")
async def process_bulk_restock(message):
    category = admin_states[message.from_user.id]
    raw_lines = message.text.strip().split("\n")
    valid_accounts = [line.strip() for line in raw_lines if line.strip()]
    count_added = len(valid_accounts)
    if count_added == 0:
        await bot.reply_to(message, "⚠️ No valid accounts detected. Action canceled.", parse_mode="HTML")
        del admin_states[message.from_user.id]
        return
    with inventory_lock:
        if category not in admin_inventory:
            admin_inventory[category] = []
        admin_inventory[category].extend(valid_accounts)
        save_inventory(admin_inventory)
    del admin_states[message.from_user.id]
    success_text = (f"✅ <b>BULK STOCK ADDED SUCCESSFULLY!</b>\n──────────────────────────\n📦 <b>Category:</b> {category}\n🔢 <b>Accounts Imported:</b> {count_added}\n🎒 <b>Current Total Stock:</b> {len(admin_inventory.get(category, []))} items")
    await bot.send_message(message.chat.id, success_text, parse_mode="HTML")

@bot.message_handler(commands=['viewinv'])
async def view_inventory(message):
    if message.from_user.id not in ADMINS:
        return
    if message.chat.type != "private":
        await bot.reply_to(message, "❌ Admin, check this via private chat to keep credentials safe!", parse_mode="HTML")
        return
    text = "🎒 <b>CURRENT BOT INVENTORY STOCKS:</b>\n\n"
    for cat, items in admin_inventory.items():
        text += f"📦 <b>{cat}</b> (Stocks: {len(items)})\n──────────────────────────\n"
        if len(items) > 0:
            for item in items:
                text += f"<code>{item}</code>\n"
        else:
            text += "<i>No stock available.</i>\n"
        text += "\n"
    await bot.send_message(message.chat.id, text, parse_mode="HTML")

@bot.message_handler(commands=['setgame'])
async def set_game(message):
    if message.from_user.id not in ADMINS:
        return
    try:
        _, args = message.text.split(" ", 1)
        if "|" not in args:
            await bot.reply_to(message, "⚠️ Format error! Use: `/setgame Name | Category`", parse_mode="HTML")
            return
        parts = args.rsplit("|", 1)
        game_name = parts[0].strip()
        prize_category = parts[1].strip()
        prize_quantity = 1
        match = re.search(r'\[(\d+)', game_name)
        if match:
            prize_quantity = int(match.group(1))
        if prize_category not in admin_inventory:
            await bot.reply_to(message, f"⚠️ Invalid Category! Use exactly: `CPM2 Regular`, `CPM2 Coins`, or `CarX Street`.", parse_mode="HTML")
            return
        chat_id = message.chat.id
        t = get_tournament(chat_id)
        t['game'] = game_name
        t['prize_cat'] = prize_category
        t['prize_qty'] = prize_quantity
        t['players'] = []
        t['eliminated_this_round'] = []
        t['last_msg_id'] = None
        t['current_round'] = 1
        t['answered_users'] = []
        t['tic_tac_toe_board'] = None
        t.pop('auto_end_at', None)
        save_tournaments()
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🎮 JOIN BRACKET", callback_data="join_game"))
        lobby_text = (
            "◢◤ <b>TNNR TOURNAMENT LOBBY</b> ◢◤\n"
            "──────────────────────────\n"
            f"🎮 <b>GAME:</b> {game_name}\n"
            f"🎁 <b>REWARD:</b> {prize_quantity}x {prize_category} Account(s)\n"
            f"👥 <b>SLOTS:</b> 0 Registered\n"
            "──────────────────────────\n"
            "» <i>Click the button below to secure your slot!</i>"
        )
        msg = await bot.send_message(message.chat.id, lobby_text, parse_mode="HTML", reply_markup=markup)
        t['last_msg_id'] = msg.message_id
        save_tournaments()
        await schedule_auto_start(chat_id, msg.message_id, min_minutes=25, max_minutes=35)
    except Exception as e:
        await bot.reply_to(message, f"⚠️ Error: {str(e)}\nFormat: /setgame Name [Qty] | Category", parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data == "join_game")
async def join_game_cb(call):
    chat_id = call.message.chat.id
    t = get_tournament(chat_id)
    user = f"@{call.from_user.username}" if call.from_user.username else call.from_user.first_name

    if user not in t.get('players', []):
        t['players'].append(user)
        save_tournaments()
        await bot.answer_callback_query(call.id, "You have joined the bracket!")
    else:
        await bot.answer_callback_query(call.id, "You are already registered!", show_alert=True)
        return

    game_name = t.get('game', 'Unknown')
    prize_cat = t.get('prize_cat', 'Unknown')
    prize_qty = t.get('prize_qty', 0)
    count = len(t.get('players', []))

    base_text = (
        "◢◤ <b>TNNR TOURNAMENT LOBBY</b> ◢◤\n"
        "──────────────────────────\n"
        f"🎮 <b>GAME:</b> {game_name}\n"
        f"🎁 <b>REWARD:</b> {prize_qty}x {prize_cat} Account(s)\n"
        f"👥 <b>SLOTS:</b> {count} Registered\n"
    )

    auto_end = t.get('auto_end_at')
    if auto_end:
        remaining = max(0, int(auto_end) - int(time.time()))
        minutes_left = remaining // 60
        seconds_left = remaining % 60
        time_left_str = f"{minutes_left}m {seconds_left}s" if minutes_left > 0 else f"{seconds_left}s"
        max_seconds = 35 * 60
        percent = min(100.0, (1 - remaining / max_seconds) * 100.0) if max_seconds > 0 else 100.0
        progress = format_progress_bar(percent, length=12)

        updated_text = (
            base_text +
            "──────────────────────────\n"
            f"⏳ <b>Auto-start in:</b> {time_left_str}\n"
            f"{progress} {percent:.0f}%\n\n"
            "» <i>Click the button below to secure your slot!</i>"
        )
    else:
        updated_text = base_text + "──────────────────────────\n» <i>Click the button below to secure your slot!</i>"

    try:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🎮 JOIN BRACKET", callback_data="join_game"))
        await bot.edit_message_text(updated_text, chat_id, t.get('last_msg_id'), parse_mode="HTML", reply_markup=markup)
    except Exception:
        pass

@bot.message_handler(commands=['startgame'])
async def start_game(message):
    if message.from_user.id not in ADMINS:
        return
    chat_id = message.chat.id
    t = get_tournament(chat_id)
    if not t.get('players'):
        await bot.reply_to(message, "❌ There are no players in the bracket yet, admin.", parse_mode="HTML")
        return
    cancel_auto_start(chat_id)
    if t.get('last_msg_id'):
        try:
            await bot.delete_message(chat_id, t['last_msg_id'])
        except Exception:
            pass
    await bot.send_message(chat_id, "🏁 <b>Round 1 — Game started!</b>", parse_mode="HTML")
    await trigger_next_round(chat_id)

# ============ TRIGGER NEXT ROUND ============
async def trigger_next_round(chat_id):
    t = get_tournament(chat_id)
    players = t.get('players', [])
    game_name = t.get('game', '')
    round_num = t.get('current_round', 1)

    t['answered_users'] = []
    t['eliminated_this_round'] = []
    save_tournaments()

    if len(players) == 1:
        await declare_champion(chat_id, [players[0]])
        return
    elif len(players) == 2 and "RPS" in game_name:
        await play_rps_bracket(chat_id, players, round_num)
        return
    elif len(players) == 2 and "Tic-Tac-Toe" in game_name:
        await play_tic_tac_toe(chat_id, players, round_num)
        return
    elif len(players) == 0:
        await bot.send_message(chat_id, "💀 <b>GAME OVER:</b> Everyone was eliminated! No winners this time.", parse_mode="HTML")
        return

    game_modes = ['Math Prodigy', 'Reaction Test', 'Russian Roulette', 'Minefield', 'Lucky Dice', 'Reflex Master', 'Safe Cracker']
    selected_game = random.choice(game_modes)
    
    if selected_game == 'Math Prodigy':
        await play_math_prodigy(chat_id, players, round_num)
    elif selected_game == 'Reaction Test':
        await play_reaction_test(chat_id, players, round_num)
    elif selected_game == 'Russian Roulette':
        await play_russian_roulette(chat_id, players, round_num)
    elif selected_game == 'Minefield':
        await play_minefield(chat_id, players, round_num)
    elif selected_game == 'Lucky Dice':
        await play_lucky_dice(chat_id, players, round_num)
    elif selected_game == 'Reflex Master':
        await play_reflex_master(chat_id, players, round_num)
    elif selected_game == 'Safe Cracker':
        await play_safe_cracker(chat_id, players, round_num)

# ============ GAME IMPLEMENTATIONS ============

# MATH PRODIGY
async def play_math_prodigy(chat_id, players, round_num):
    q_data = random.choice(HARDCORE_QUESTIONS)
    correct = q_data['a']
    choices = list(set([str(int(correct) + random.choice([-2, 1, 3])), str(int(correct) - 2), correct]))
    random.shuffle(choices)
    markup = types.InlineKeyboardMarkup()
    buttons = [types.InlineKeyboardButton(text, callback_data=f"mathprodigy_{text}||{correct}") for text in choices]
    markup.add(*buttons)
    round_text = (
        f"╔════════════════════════╗\n"
        f"  🧮 <b>MATH PRODIGY — ROUND {round_num}</b>\n"
        f"╚════════════════════════╝\n"
        f"👥 <b>ALIVE:</b> {', '.join(players)}\n\n"
        f"🧠 <b>SOLVE FAST:</b> <code>{q_data['q']}</code>\n\n"
        f"⏳ 12 SECONDS TIMER!"
    )
    msg = await bot.send_message(chat_id, round_text, parse_mode="HTML", reply_markup=markup)
    await asyncio.sleep(12)
    await process_round_results(chat_id, msg, players)

# REACTION TEST
async def play_reaction_test(chat_id, players, round_num):
    target = random.choice(["💎", "🔮", "💍"])
    items = ["👁️", "📦", "🔮", "💧", "💎", "💍"]
    random.shuffle(items)
    markup = types.InlineKeyboardMarkup()
    buttons = [types.InlineKeyboardButton(item, callback_data=f"reactiontest_{item}||{target}") for item in items]
    markup.add(*buttons[:3])
    markup.add(*buttons[3:])
    round_text = (
        f"⚡ <b>REACTION TEST — ROUND {round_num}</b>\n"
        f"👥 <b>ALIVE:</b> {', '.join(players)}\n\n"
        f"🎯 <b>FIND THE TARGET:</b> {target}\n\n"
        f"⏳ 8 SECONDS!"
    )
    msg = await bot.send_message(chat_id, round_text, parse_mode="HTML", reply_markup=markup)
    await asyncio.sleep(8)
    await process_round_results(chat_id, msg, players)

# RUSSIAN ROULETTE
async def play_russian_roulette(chat_id, players, round_num):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔫 PULL THE TRIGGER", callback_data="russianroulette_pull||roulette"))
    round_text = (
        f"🔫 <b>RUSSIAN ROULETTE — ROUND {round_num}</b>\n"
        f"👥 <b>ALIVE:</b> {', '.join(players)}\n\n"
        f"Press the button to test your luck!\n\n"
        f"⏳ 10 SECONDS!"
    )
    msg = await bot.send_message(chat_id, round_text, parse_mode="HTML", reply_markup=markup)
    await asyncio.sleep(10)
    await process_round_results(chat_id, msg, players)

# MINEFIELD
async def play_minefield(chat_id, players, round_num):
    bomb_door = random.choice(['1', '2', '3', '4'])
    markup = types.InlineKeyboardMarkup()
    markup.row(types.InlineKeyboardButton("🚪 DOOR 1", callback_data=f"minefield_1||{bomb_door}"),
               types.InlineKeyboardButton("🚪 DOOR 2", callback_data=f"minefield_2||{bomb_door}"))
    markup.row(types.InlineKeyboardButton("🚪 DOOR 3", callback_data=f"minefield_3||{bomb_door}"),
               types.InlineKeyboardButton("🚪 DOOR 4", callback_data=f"minefield_4||{bomb_door}"))
    round_text = (
        f"🎮 <b>MINEFIELD — ROUND {round_num}</b>\n"
        f"👥 <b>ALIVE:</b> {', '.join(players)}\n\n"
        f"🚪 <b>CHOOSE A DOOR:</b>\n"
        f"⚠️ One of the doors contains a BOMB!\n\n"
        f"⏳ 10 SECONDS!"
    )
    msg = await bot.send_message(chat_id, round_text, parse_mode="HTML", reply_markup=markup)
    await asyncio.sleep(10)
    await process_round_results(chat_id, msg, players)

# LUCKY DICE
async def play_lucky_dice(chat_id, players, round_num):
    lucky_number = random.choice(['EVEN', 'ODD'])
    markup = types.InlineKeyboardMarkup()
    markup.row(types.InlineKeyboardButton("🎲 EVEN", callback_data=f"luckydice_EVEN||{lucky_number}"),
               types.InlineKeyboardButton("🎲 ODD", callback_data=f"luckydice_ODD||{lucky_number}"))
    round_text = (
        f"🎰 <b>LUCKY DICE — ROUND {round_num}</b>\n"
        f"👥 <b>ALIVE:</b> {', '.join(players)}\n\n"
        f"🎲 The bot rolled the dice! Choose EVEN or ODD!\n\n"
        f"⏳ 10 SECONDS!"
    )
    msg = await bot.send_message(chat_id, round_text, parse_mode="HTML", reply_markup=markup)
    await asyncio.sleep(10)
    await process_round_results(chat_id, msg, players)

# REFLEX MASTER
async def play_reflex_master(chat_id, players, round_num):
    green_btn = random.choice(['LEFT', 'CENTER', 'RIGHT'])
    markup = types.InlineKeyboardMarkup()
    if green_btn == 'LEFT':
        markup.row(types.InlineKeyboardButton("🟢 TAP!", callback_data=f"reflexmaster_GREEN||{green_btn}"),
                   types.InlineKeyboardButton("🔴 STOP", callback_data=f"reflexmaster_RED1||{green_btn}"),
                   types.InlineKeyboardButton("🔴 STOP", callback_data=f"reflexmaster_RED2||{green_btn}"))
    elif green_btn == 'CENTER':
        markup.row(types.InlineKeyboardButton("🔴 STOP", callback_data=f"reflexmaster_RED1||{green_btn}"),
                   types.InlineKeyboardButton("🟢 TAP!", callback_data=f"reflexmaster_GREEN||{green_btn}"),
                   types.InlineKeyboardButton("🔴 STOP", callback_data=f"reflexmaster_RED2||{green_btn}"))
    else:
        markup.row(types.InlineKeyboardButton("🔴 STOP", callback_data=f"reflexmaster_RED1||{green_btn}"),
                   types.InlineKeyboardButton("🔴 STOP", callback_data=f"reflexmaster_RED2||{green_btn}"),
                   types.InlineKeyboardButton("🟢 TAP!", callback_data=f"reflexmaster_GREEN||{green_btn}"))
    round_text = (
        f"⚡ <b>REFLEX MASTER — ROUND {round_num}</b>\n"
        f"👥 <b>ALIVE:</b> {', '.join(players)}\n\n"
        f"🟢 <b>HIT THE GREEN LIGHT ONLY!</b>\n\n"
        f"⏳ 8 SECONDS!"
    )
    msg = await bot.send_message(chat_id, round_text, parse_mode="HTML", reply_markup=markup)
    await asyncio.sleep(8)
    await process_round_results(chat_id, msg, players)

# SAFE CRACKER
async def play_safe_cracker(chat_id, players, round_num):
    safe_choice = random.choice(['EVEN', 'ODD'])
    markup = types.InlineKeyboardMarkup()
    markup.row(types.InlineKeyboardButton("🔢 EVEN", callback_data=f"safecracker_EVEN||{safe_choice}"),
               types.InlineKeyboardButton("🔠 ODD", callback_data=f"safecracker_ODD||{safe_choice}"))
    round_text = (
        f"🔒 <b>SAFE CRACKER — ROUND {round_num}</b>\n"
        f"👥 <b>ALIVE:</b> {', '.join(players)}\n\n"
        f"🎰 The bot picked EVEN or ODD! Guess right!\n\n"
        f"⏳ 10 SECONDS!"
    )
    msg = await bot.send_message(chat_id, round_text, parse_mode="HTML", reply_markup=markup)
    await asyncio.sleep(10)
    await process_round_results(chat_id, msg, players)

# RPS BRACKET - ENGLISH VERSION
async def play_rps_bracket(chat_id, players, round_num):
    bot_choice = random.choice(['ROCK', 'PAPER', 'SCISSORS'])
    markup = types.InlineKeyboardMarkup()
    markup.row(types.InlineKeyboardButton("🪨 ROCK", callback_data=f"rpsgame_ROCK||{bot_choice}"),
               types.InlineKeyboardButton("📄 PAPER", callback_data=f"rpsgame_PAPER||{bot_choice}"),
               types.InlineKeyboardButton("✂️ SCISSORS", callback_data=f"rpsgame_SCISSORS||{bot_choice}"))
    round_text = (
        f"⚔️ <b>ROCK PAPER SCISSORS — FINAL</b>\n"
        f"🎮 <b>GAME:</b> Rock, Paper, Scissors\n"
        f"👥 <b>PLAYERS:</b> {' vs '.join(players)}\n\n"
        f"🤖 <b>BOT CHOICE:</b> ??? (Hidden)\n\n"
        f"⏳ 12 SECONDS!"
    )
    msg = await bot.send_message(chat_id, round_text, parse_mode="HTML", reply_markup=markup)
    await asyncio.sleep(12)
    await process_rps_results(chat_id, msg, players, bot_choice)

# TIC-TAC-TOE - FIXED 3x3 GRID
async def play_tic_tac_toe(chat_id, players, round_num):
    await play_tic_tac_toe_round(chat_id, [' ' for _ in range(9)], players, 0, 15)

async def play_tic_tac_toe_round(chat_id, board, players, current_player, timer):
    if timer <= 0:
        other_player = players[1 - current_player]
        await declare_champion(chat_id, [other_player])
        return
    
    def get_board_display():
        display = ""
        for i in range(3):
            row_start = i * 3
            row_end = row_start + 3
            row_cells = board[row_start:row_end]
            row_display = ""
            for cell in row_cells:
                if cell == 'X':
                    row_display += "[❌]"
                elif cell == 'O':
                    row_display += "[⭕]"
                else:
                    row_display += "[ ]"
            display += row_display + "\n"
        return display.strip()
    
    player_name = players[current_player]
    board_display = get_board_display()
    markup = types.InlineKeyboardMarkup()
    
    # Create 3x3 grid with proper positioning
    for i in range(3):
        row_buttons = []
        for j in range(3):
            idx = i * 3 + j
            if board[idx] == ' ':
                btn_text = str(idx + 1)
                row_buttons.append(types.InlineKeyboardButton(btn_text, callback_data=f"tictactoe_{idx}||{current_player}"))
            else:
                # Show occupied cell (non-clickable display)
                symbol = "❌" if board[idx] == 'X' else "⭕"
                row_buttons.append(types.InlineKeyboardButton(symbol, callback_data=f"tictactoe_blocked_{idx}"))
        markup.row(*row_buttons)
    
    round_text = (
        f"⚔️ <b>TIC-TAC-TOE FINAL</b>\n"
        f"{players[0]} ❌ vs {players[1]} ⭕\n\n"
        f"🎯 <b>Current Turn:</b> {player_name}\n\n"
        f"{board_display}\n\n"
        f"⏳ {timer} SECONDS REMAINING!"
    )
    msg = await bot.send_message(chat_id, round_text, parse_mode="HTML", reply_markup=markup)
    t = get_tournament(chat_id)
    t['tic_tac_toe_board'] = board
    t['tic_tac_toe_current'] = current_player
    t['tic_tac_toe_players'] = players
    t['tic_tac_toe_msg_id'] = msg.message_id
    t['tic_tac_toe_timer'] = timer
    save_tournaments()

# ============ RESULT PROCESSING ============
async def process_round_results(chat_id, msg, players):
    t = get_tournament(chat_id)
    answered = t.get('answered_users', [])
    eliminated = list(set(players) - set(answered))
    for player in eliminated:
        if player in t['players']:
            t['players'].remove(player)
    t['current_round'] = t.get('current_round', 1) + 1
    save_tournaments()
    try:
        await bot.delete_message(chat_id, msg.message_id)
    except Exception:
        pass
    await asyncio.sleep(1)
    await trigger_next_round(chat_id)

async def process_rps_results(chat_id, msg, players, bot_choice):
    t = get_tournament(chat_id)
    answered = t.get('answered_users', [])
    survivors = []
    for player_choice in answered:
        if check_rps_winner(player_choice, bot_choice):
            survivors.append(player_choice)
    eliminated = list(set(players) - set(survivors))
    for player in eliminated:
        if player in t['players']:
            t['players'].remove(player)
    t['current_round'] = t.get('current_round', 1) + 1
    save_tournaments()
    try:
        await bot.delete_message(chat_id, msg.message_id)
    except Exception:
        pass
    await asyncio.sleep(1)
    await trigger_next_round(chat_id)

def check_rps_winner(player_choice, bot_choice):
    wins = {'ROCK': 'SCISSORS', 'PAPER': 'ROCK', 'SCISSORS': 'PAPER'}
    return wins.get(player_choice) == bot_choice or player_choice == bot_choice

# ============ CALLBACK HANDLERS ============

# MATH PRODIGY
@bot.callback_query_handler(func=lambda call: call.data.startswith('mathprodigy_'))
async def handle_math_prodigy(call):
    chat_id = call.message.chat.id
    t = get_tournament(chat_id)
    user = f"@{call.from_user.username}" if call.from_user.username else call.from_user.first_name
    if user not in t.get('players', []):
        await bot.answer_callback_query(call.id, "You are just a spectator!", show_alert=True)
        return
    if user in t.get('answered_users', []):
        await bot.answer_callback_query(call.id, "You already answered!", show_alert=True)
        return
    data_parts = call.data.replace('mathprodigy_', '').split('||')
    selected = data_parts[0]
    correct = data_parts[1]
    if selected == correct:
        t['answered_users'].append(user)
        save_tournaments()
        await bot.answer_callback_query(call.id, "✅ Correct! You're safe!")
    else:
        await bot.answer_callback_query(call.id, "💥 WRONG! ELIMINATED!", show_alert=True)

# REACTION TEST
@bot.callback_query_handler(func=lambda call: call.data.startswith('reactiontest_'))
async def handle_reaction_test(call):
    chat_id = call.message.chat.id
    t = get_tournament(chat_id)
    user = f"@{call.from_user.username}" if call.from_user.username else call.from_user.first_name
    if user not in t.get('players', []):
        return
    data = call.data.replace('reactiontest_', '').split('||')
    chosen = data[0]
    target = data[1]
    if chosen == target:
        if user not in t.get('answered_users', []):
            t['answered_users'].append(user)
            save_tournaments()
            await bot.answer_callback_query(call.id, "✅ Found it! You're safe!")
    else:
        await bot.answer_callback_query(call.id, "❌ Wrong! ELIMINATED!", show_alert=True)

# RUSSIAN ROULETTE
@bot.callback_query_handler(func=lambda call: call.data.startswith('russianroulette_'))
async def handle_russian_roulette(call):
    chat_id = call.message.chat.id
    t = get_tournament(chat_id)
    user = f"@{call.from_user.username}" if call.from_user.username else call.from_user.first_name
    if user not in t.get('players', []):
        return
    if user not in t.get('answered_users', []):
        if random.choice([True, False, False, False]):
            await bot.answer_callback_query(call.id, "💥 BOOM! You're eliminated!", show_alert=True)
        else:
            t['answered_users'].append(user)
            save_tournaments()
            await bot.answer_callback_query(call.id, "✅ Click... You lived!")

# MINEFIELD
@bot.callback_query_handler(func=lambda call: call.data.startswith('minefield_'))
async def handle_minefield(call):
    chat_id = call.message.chat.id
    t = get_tournament(chat_id)
    user = f"@{call.from_user.username}" if call.from_user.username else call.from_user.first_name
    if user not in t.get('players', []):
        return
    data = call.data.replace('minefield_', '').split('||')
    chosen = data[0]
    bomb = data[1]
    if chosen == bomb:
        await bot.answer_callback_query(call.id, "💣 BOOM! ELIMINATED!", show_alert=True)
    else:
        if user not in t.get('answered_users', []):
            t['answered_users'].append(user)
            save_tournaments()
            await bot.answer_callback_query(call.id, "✅ Safe! You advance!")

# LUCKY DICE
@bot.callback_query_handler(func=lambda call: call.data.startswith('luckydice_'))
async def handle_lucky_dice(call):
    chat_id = call.message.chat.id
    t = get_tournament(chat_id)
    user = f"@{call.from_user.username}" if call.from_user.username else call.from_user.first_name
    if user not in t.get('players', []):
        return
    data = call.data.replace('luckydice_', '').split('||')
    chosen = data[0]
    correct = data[1]
    if chosen == correct:
        if user not in t.get('answered_users', []):
            t['answered_users'].append(user)
            save_tournaments()
            await bot.answer_callback_query(call.id, "🎉 Lucky! You pass!")
    else:
        await bot.answer_callback_query(call.id, "❌ Bad luck! ELIMINATED!", show_alert=True)

# REFLEX MASTER
@bot.callback_query_handler(func=lambda call: call.data.startswith('reflexmaster_'))
async def handle_reflex_master(call):
    chat_id = call.message.chat.id
    t = get_tournament(chat_id)
    user = f"@{call.from_user.username}" if call.from_user.username else call.from_user.first_name
    if user not in t.get('players', []):
        return
    data = call.data.replace('reflexmaster_', '').split('||')
    chosen = data[0]
    if chosen == 'GREEN':
        if user not in t.get('answered_users', []):
            t['answered_users'].append(user)
            save_tournaments()
            await bot.answer_callback_query(call.id, "⚡ Perfect! You're safe!")
    else:
        await bot.answer_callback_query(call.id, "❌ Wrong! ELIMINATED!", show_alert=True)

# SAFE CRACKER
@bot.callback_query_handler(func=lambda call: call.data.startswith('safecracker_'))
async def handle_safe_cracker(call):
    chat_id = call.message.chat.id
    t = get_tournament(chat_id)
    user = f"@{call.from_user.username}" if call.from_user.username else call.from_user.first_name
    if user not in t.get('players', []):
        return
    data = call.data.replace('safecracker_', '').split('||')
    chosen = data[0]
    correct = data[1]
    if chosen == correct:
        if user not in t.get('answered_users', []):
            t['answered_users'].append(user)
            save_tournaments()
            await bot.answer_callback_query(call.id, "🎉 You pass!")
    else:
        await bot.answer_callback_query(call.id, "❌ Bad luck! ELIMINATED!", show_alert=True)

# RPS BRACKET - ENGLISH
@bot.callback_query_handler(func=lambda call: call.data.startswith('rpsgame_'))
async def handle_rps_bracket(call):
    chat_id = call.message.chat.id
    t = get_tournament(chat_id)
    user = f"@{call.from_user.username}" if call.from_user.username else call.from_user.first_name
    if user not in t.get('players', []):
        return
    data = call.data.replace('rpsgame_', '').split('||')
    chosen = data[0]
    bot_choice = data[1]
    if check_rps_winner(chosen, bot_choice):
        if user not in t.get('answered_users', []):
            t['answered_users'].append(user)
            save_tournaments()
            await bot.answer_callback_query(call.id, "✅ Win/Tie! You're safe!")
    else:
        await bot.answer_callback_query(call.id, "💥 You LOSE! ELIMINATED!", show_alert=True)

# TIC-TAC-TOE - 3x3 GRID
@bot.callback_query_handler(func=lambda call: call.data.startswith('tictactoe_'))
async def handle_tic_tac_toe(call):
    chat_id = call.message.chat.id
    t = get_tournament(chat_id)
    user = f"@{call.from_user.username}" if call.from_user.username else call.from_user.first_name
    
    # Ignore blocked buttons
    if 'blocked' in call.data:
        await bot.answer_callback_query(call.id, "Cell already taken!", show_alert=False)
        return
    
    data = call.data.replace('tictactoe_', '').split('||')
    position = int(data[0])
    player_idx = int(data[1])
    players = t.get('tic_tac_toe_players', [])
    if not players or user != players[player_idx]:
        await bot.answer_callback_query(call.id, "Not your turn!", show_alert=True)
        return
    board = t.get('tic_tac_toe_board', [])
    if board[position] != ' ':
        await bot.answer_callback_query(call.id, "Already taken!", show_alert=True)
        return
    board[position] = 'X' if player_idx == 0 else 'O'
    
    win_patterns = [[0,1,2], [3,4,5], [6,7,8], [0,3,6], [1,4,7], [2,5,8], [0,4,8], [2,4,6]]
    for pattern in win_patterns:
        if board[pattern[0]] == board[pattern[1]] == board[pattern[2]] != ' ':
            await bot.answer_callback_query(call.id, "🎉 You won!")
            await declare_champion(call.message.chat.id, [players[player_idx]])
            return
    
    if all(cell != ' ' for cell in board):
        await bot.answer_callback_query(call.id, "Draw! Random winner...")
        await declare_champion(call.message.chat.id, [random.choice(players)])
        return
    
    t['tic_tac_toe_board'] = board
    t['tic_tac_toe_current'] = 1 - player_idx
    save_tournaments()
    
    await bot.answer_callback_query(call.id, "✅ Move made!")
    await play_tic_tac_toe_round(chat_id, board, players, 1 - player_idx, t.get('tic_tac_toe_timer', 15) - 1)

# ============ DECLARE CHAMPION ============
async def declare_champion(chat_id, winners):
    t = get_tournament(chat_id)
    prize_category = t.get('prize_cat')
    prize_quantity = t.get('prize_qty', 0)
    total_winners = len(winners)
    prize_per_winner = prize_quantity // total_winners if total_winners > 0 else 0
    remainder = prize_quantity % total_winners if total_winners > 0 else 0
    
    for idx, winner in enumerate(winners):
        qty = prize_per_winner + (1 if idx < remainder else 0)
        secret_code = f"GIFT-{random.randint(10000, 99999)}"
        with claim_tokens_lock:
            claim_tokens[secret_code] = {"winners": winners, "winner": winner, "category": prize_category, "quantity": qty, "group_size": total_winners}
            save_claim_tokens(claim_tokens)
        add_win_to_leaderboard(winner)
        
        bot_info = await bot.get_me()
        clean_url = "t.me/" + bot_info.username
        
        if total_winners > 1:
            champion_text = (f"👑 <b>GROUP WINNERS!</b> 👑\n━━━━━━━━━━━━━━━━━━━━━━━━━━\nYour team won! {', '.join(winners)}\n\n🎁 <b>PRIZE SPLIT (÷{total_winners}):</b>\n👤 {winner} gets: {qty}x {prize_category}\n\n🎫 <b>CODE:</b> <code>{secret_code}</code>\n📥 <b>CLAIM:</b> /claim {secret_code}")
        else:
            champion_text = (f"👑 <b>GRAND CHAMPION!</b> 👑\n━━━━━━━━━━━━━━━━━━━━━━━━━━\nYou survived the gauntlet, {winner}!\n🏆 +1 Win registered!\n\n🎫 <b>CODE:</b> <code>{secret_code}</code>\n📥 <b>CLAIM:</b> /claim {secret_code}")
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📥 CLAIM VIA VM", url=clean_url))
        await bot.send_message(chat_id, champion_text, parse_mode="HTML", reply_markup=markup)

@bot.message_handler(commands=['claim'])
async def claim_reward(message):
    if message.chat.type != "private":
        return
    try:
        _, code = message.text.split(" ", 1)
        code = code.strip()
    except ValueError:
        await bot.reply_to(message, "⚠️ Format: /claim GIFT-XXXX", parse_mode="HTML")
        return
    
    if code not in claim_tokens:
        await bot.reply_to(message, "❌ Invalid or expired code.", parse_mode="HTML")
        return
    
    token_info = claim_tokens[code]
    sender_username = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name
    
    if sender_username != token_info['winner']:
        await bot.reply_to(message, "❌ You are not the registered winner for this code.", parse_mode="HTML")
        return
    
    category = token_info['category']
    requested_qty = token_info['quantity']
    group_size = token_info.get('group_size', 1)
    
    with inventory_lock:
        available_stock = len(admin_inventory.get(category, []))
        dispense_qty = min(requested_qty, available_stock)
        dispensed_prizes = []
        for _ in range(dispense_qty):
            dispensed_prizes.append(admin_inventory[category].pop(0))
        save_inventory(admin_inventory)
    
    with claim_tokens_lock:
        if code in claim_tokens:
            del claim_tokens[code]
            save_claim_tokens(claim_tokens)
    
    prize_box_text = "\n".join(dispensed_prizes)
    
    if group_size > 1:
        vm_success_template = ("🎉 <b>GROUP PRIZE CLAIMED!</b> 🎉\n━━━━━━━━━━━━━━━━━━━━━━━━━━\nYour group crushed it! Prize divided equally.\n\n<b>📊 Your Share:</b>\n👤 {player}\n👥 Group Size: {group} players\n🎁 Your Accounts: {qty}\n\n<pre>{accounts}</pre>\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n⚡ Great teamwork! 🔥")
        message_text = vm_success_template.format(player=token_info['winner'], group=group_size, qty=dispense_qty, accounts=prize_box_text)
    else:
        vm_success_template = ("🎉 <b>CONGRATULATIONS!</b> 🎉\n━━━━━━━━━━━━━━━━━━━━━━━━━━\nYou dominated the tournament!\n\n<b>🎁 YOUR REWARD:</b>\n🎮 {category}\n🔢 {qty} account(s)\n\n<pre>{accounts}</pre>\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n⚡ Stay active for more tournaments! 🔥")
        message_text = vm_success_template.format(category=category, qty=dispense_qty, accounts=prize_box_text)
    
    await bot.send_message(message.chat.id, message_text, parse_mode="HTML")

# ============ STARTUP ============
async def restore_auto_starts():
    now = int(time.time())
    for key, t in tournaments.items():
        chat_id = int(key)
        end_ts = t.get('auto_end_at')
        if end_ts and end_ts > now:
            try:
                task = asyncio.create_task(_auto_countdown(chat_id))
                auto_tasks[chat_id] = task
            except Exception as e:
                print("Failed to restore auto-start for chat", chat_id, e)
        else:
            if end_ts and end_ts <= now:
                t.pop('auto_end_at', None)
    save_tournaments()

if __name__ == '__main__':
    async def main():
        await restore_auto_starts()
        await bot.polling(non_stop=True)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Shutting down bot...")
