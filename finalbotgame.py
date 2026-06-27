import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import json
import random
import time
import os
import string
import threading

# ==========================================
# ⚙️ CONFIGURATION & CREDENTIALS
# ==========================================
TOKEN = "8905207289:AAH6rvfkQ--Z2TE9QKCU1SyLkMkGXcGGmgA"
GROUP_ID = -1003994249946
OWNER_ID = 6531314640
EXTRA_ADMIN = 8650959684
EXTRA_ADMIN_2 = 8649387707  # 👈 Eto yung bagong admin ID na dinagdag natin, bro

# Pinagsama-sama silang tatlo sa loob ng listahan ng mga authorized admins
ADMINS = [OWNER_ID, EXTRA_ADMIN, EXTRA_ADMIN_2]


bot = telebot.TeleBot(TOKEN)

# ==========================================
# 💾 DATABASE MANAGEMENT (JSON SAVE)
# ==========================================
DB_FILES = {
    "inventory": "inventory.json",
    "players": "players.json",
    "claims": "claims.json"
}

def load_data(file_name):
    if not os.path.exists(file_name): return {}
    try:
        with open(file_name, 'r') as f: return json.load(f)
    except:
        return {}

def save_data(file_name, data):
    with open(file_name, 'w') as f:
        json.dump(data, f, indent=4)

inventory_db = load_data(DB_FILES["inventory"])
if not inventory_db:
    inventory_db = {"CPM2 Regular": [], "CPM2 Coins": [], "CarX Street": []}
    save_data(DB_FILES["inventory"], inventory_db)

# ==========================================
# 🎮 GAME ENGINE STATE
# ==========================================
game_state = {
    "active": False,
    "name": "",
    "prize_count": 0,
    "prize_cat": "",
    "phase": "idle",
    "players": [],
    "groups": {"Green": [], "Blue": [], "Red": [], "Yellow": []},
    "round": 0,
    "msg_id": None,
    "turn": None,
    "extra_data": {},
    "timer_thread": None
}

def cancel_timer():
    if game_state.get("timer_thread"):
        game_state["timer_thread"].cancel()
        game_state["timer_thread"] = None

# ==========================================
# 🛠️ ADMIN INVENTORY SYSTEM
# ==========================================
user_add_state = {}

@bot.message_handler(commands=['addinv'])
def addinv_cmd(message):
    if message.from_user.id not in ADMINS: return
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🚘 REGULAR ACCOUNT 🚘", callback_data="add_CPM2 Regular"))
    markup.add(InlineKeyboardButton("🔘🏎 12K COIN ACCOUNT 🏎🔘", callback_data="add_CPM2 Coins"))
    markup.add(InlineKeyboardButton("🚔 CarX Street ☠️", callback_data="add_CarX Street"))
    bot.send_message(message.chat.id, "<b>Select Category to Add Accounts, Bro:</b>", reply_markup=markup, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data.startswith("add_"))
def process_add_category(call):
    if call.from_user.id not in ADMINS: return
    category = call.data.split("_")[1]
    msg = bot.send_message(call.message.chat.id, f"Send me the accounts for <b>{category}</b> bro (format email:pass, one per line):", parse_mode="HTML")
    user_add_state[call.from_user.id] = category
    bot.register_next_step_handler(msg, save_accounts)

def save_accounts(message):
    if message.from_user.id not in user_add_state: return
    category = user_add_state.pop(message.from_user.id)
    accounts = message.text.strip().split('\n')
    valid_accs = [acc.strip() for acc in accounts if ':' in acc]
    
    inv_db = load_data(DB_FILES["inventory"])
    inv_db[category].extend(valid_accs)
    save_data(DB_FILES["inventory"], inv_db)
    bot.send_message(message.chat.id, f"✅ Successfully added {len(valid_accs)} accounts to {category}, bro!")

@bot.message_handler(commands=['viewinv'])
def viewinv_cmd(message):
    if message.from_user.id not in ADMINS: return
    inv_db = load_data(DB_FILES["inventory"])
    text = "📦 <b>ADMIN INVENTORY STOCK</b> 📦\n───────────────────────\n"
    for cat, items in inv_db.items():
        text += f"➥ {cat}: <b>{len(items)} accounts</b>\n"
        for item in items:
            text += f"<code>{item}</code>\n"
        text += "───────────────────────\n"
    bot.send_message(message.from_user.id, text, parse_mode="HTML")
    if message.chat.type != "private":
        bot.reply_to(message, "I sent the inventory to your PM so others won't see it, bro! 🤫")

# ==========================================
# 🎁 REWARD & CLAIM SYSTEM
# ==========================================
def generate_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

def distribute_prize(winners):
    global game_state
    inv_db = load_data(DB_FILES["inventory"])
    claims_db = load_data(DB_FILES["claims"])
    players_db = load_data(DB_FILES["players"])
    
    cat = game_state["prize_cat"]
    count = game_state["prize_count"]
    
    available = len(inv_db.get(cat, []))
    if available < count:
        bot.send_message(GROUP_ID, f"⚠️ Admin bro! Not enough stock for {cat}! (Needed {count}, got {available})")
        return

    accs_to_give = [inv_db[cat].pop(0) for _ in range(count)]
    save_data(DB_FILES["inventory"], inv_db)
    
    num_winners = len(winners)
    base_dist = count // num_winners
    extra = count % num_winners
    
    acc_idx = 0
    for i, winner in enumerate(winners):
        to_receive = base_dist + (1 if i < extra else 0)
        for _ in range(to_receive):
            code = generate_code()
            item = accs_to_give[acc_idx]
            
            p_id = str(winner['id'])
            if p_id not in players_db:
                players_db[p_id] = {"warnings": 0, "banned_until": 0, "wins": 0, "points": 0, "inventory": [], "username": winner['username']}
            
            players_db[p_id]["wins"] += 1
            players_db[p_id]["points"] += 150
            players_db[p_id]["username"] = winner['username']
            players_db[p_id]["inventory"].append(item)
            claims_db[code] = {"item": item, "winner_id": winner['id'], "claimed": False}
            
            save_data(DB_FILES["players"], players_db)
            save_data(DB_FILES["claims"], claims_db)

            bot.send_message(GROUP_ID, f"🎉 @{winner['username']}, here is your redeem code: <code>{code}</code>\nType <code>/claim {code}</code> to reveal your prize in PM!", parse_mode="HTML")
            acc_idx += 1

@bot.message_handler(commands=['claim'])
def claim_cmd(message):
    args = message.text.split()
    p_id = str(message.from_user.id)
    players_db = load_data(DB_FILES["players"])
    
    if p_id not in players_db:
        players_db[p_id] = {"warnings": 0, "banned_until": 0, "wins": 0, "points": 0, "inventory": [], "username": message.from_user.username}

    if time.time() < players_db[p_id].get("banned_until", 0):
        bot.reply_to(message, "🚫 Bro, you are BANNED for spamming/cheating. You cannot claim right now.")
        return

    if len(args) < 2:
        bot.reply_to(message, "Use: <code>/claim CODE</code>", parse_mode="HTML")
        return
    
    code = args[1]
    claims_db = load_data(DB_FILES["claims"])
    
    if code not in claims_db or claims_db[code]["claimed"] or claims_db[code]["winner_id"] != message.from_user.id:
        players_db[p_id]["warnings"] += 1
        warns = players_db[p_id]["warnings"]
        
        if warns >= 10:
            players_db[p_id]["banned_until"] = time.time() + (3 * 3600)
            bot.reply_to(message, "🚫 <b>BANNED FOR 3 HOURS!</b> You reached 10 warnings for fake codes.", parse_mode="HTML")
        elif warns >= 5:
            bot.reply_to(message, "⚠️⚠️ <b>WARNING DON'T DO THAT</b> ⚠️⚠️\nStop using fake codes bro!", parse_mode="HTML")
        else:
            bot.reply_to(message, "⚠️ Don’t do this again if you don’t want to get banned from this bot ⚠️\nInvalid code bro!")
        save_data(DB_FILES["players"], players_db)
        return

    item = claims_db[code]["item"]
    claims_db[code]["claimed"] = True
    save_data(DB_FILES["claims"], claims_db)
    
    dm_text = f"☄️🚘 <b>TNNR REWARD SYSTEM THANKS FOR PLAYING BRO BRO</b> 🚘📦\n───────────────────────\n🎉 CONGRATULATIONS, CHAMP!\nYou won the Tournament Grand Prize!\n🎁 YOUR REWARD:\n<code>{item}</code>\n\nThank you for playing! Type /myowninventory to check your personal claims."
    try:
        bot.send_message(message.from_user.id, dm_text, parse_mode="HTML")
        bot.reply_to(message, "✅ Claimed successfully bro! Check your PMs.")
    except:
        bot.reply_to(message, "⚠️ I couldn't PM you bro! Message me first. (Don't worry, the prize is already saved in your /myowninventory!)")

@bot.message_handler(commands=['myowninventory'])
def myinv_cmd(message):
    p_id = str(message.from_user.id)
    players_db = load_data(DB_FILES["players"])
    if p_id not in players_db or not players_db[p_id]["inventory"]:
        bot.send_message(message.from_user.id, "You don't have any claimed accounts yet bro!")
        return
    
    text = "🎒 <b>YOUR PERSONAL INVENTORY</b> 🎒\n───────────────────────\n"
    for item in players_db[p_id]["inventory"]:
        text += f"🔹 <code>{item}</code>\n"
    bot.send_message(message.from_user.id, text, parse_mode="HTML")

@bot.message_handler(commands=['leaderboard'])
def leaderboard_cmd(message):
    players_db = load_data(DB_FILES["players"])
    # Kunin ang top 10
    sorted_players = sorted(players_db.items(), key=lambda x: x[1].get("points", 0), reverse=True)[:10]
    
    text = "◢◤ <b>TNNR HALL OF FAME</b> ◢◤\n──────────────────────────\n👑 TOP TOURNAMENT DOMINATORS\n"
    
    # Dinagdagan ko ng medals para sa 6th-10th place
    medals = ["🥇 1st", "🥈 2nd", "🥉 3rd", "🎖️ 4th", "🎖️ 5th", "🏅 6th", "🏅 7th", "🏅 8th", "🏅 9th", "🏅 10th"]
    
    for i, (p_id, data) in enumerate(sorted_players):
        # Inalis ko na yung "if i >= 5: break" para ituloy hanggang 10
        uname = data.get("username", f"User_{p_id[-4:]}")
        text += f"{medals[i]} ➔ @{uname} (ID: <code>{p_id}</code>) 💎 {data.get('points',0)} pts [🏆 {data.get('wins',0)} Wins]\n"
    
    text += "\n⏱️ Updates every time a match ends. Keep winning to stay on top!"
    bot.send_message(message.chat.id, text, parse_mode="HTML")

# ==========================================
# 🎮 GAME SETUP, JOINING & AUTO-START
# ==========================================
GAME_DESCRIPTIONS = {
    "russian roulette": "Spin. Pull. Pray. 💥 The game is simple: One bullet, five chances, and zero mercy. You have 15 seconds to pull the trigger or face immediate elimination. The last one standing takes the crown. Who's next? 🔫💀",
    "tic tac toe": "The classic 1v1 strategy! Outsmart your opponent and connect 3 to dominate the board. ❌⭕️",
    "time bomb": "The bomb is ticking! 💣 Pass it fast (10s timer) but don't pass back to the last person who gave it to you. Don't be the one left holding it! 🧨",
    "rps showdown": "Rock, Paper, Scissors! Choose wisely and lock it in. No backing out once you commit—mind games only! ✊✋✌️",
    "reaction test": "How fast are your reflexes? Press the button the moment it appears! Only the quickest survive. ⚡️⏱️",
    "lucky dice": "Roll together! 🎲 Lowest score gets eliminated every round. Survive the rolls or get kicked out! 📉",
    "chat assassin": "Target acquired! Choose to kill or spare. If you spare, there's a 50/50 chance you're the next victim! ⚔️🔪",
    "math prodigy": "Car & Math hardcore quiz! 🏎️💨 Be the fastest to hit the right answer. Only the smartest speedsters win! 🧠🧮 And bro you need to write the full for more exciting 😎 ⚠️DON'T USE ANY LETTER, ONLY NUMBERS⚠️",
    "treasure hunt": "12 Boxes: 6 Bombs 💣, 4 Empty 💨, 1 Super Bomb ☢️, and 1 Grand Prize 🏆. Find the prize to win instantly! Watch out for the Super Bomb—it eliminates you AND the next player! 💀💥 GOODLUCK 💀",
    "triple luck": "Group Slot Machine! 🎰 Spin for your life (15s timer). Miss your turn and you're out! Max 4 players, only the luckiest survive. 🍀"
}

def auto_start_countdown():
    global game_state
    # Check kung dapat bang magsimula
    if not game_state.get("active") or game_state.get("phase") != "joining": 
        return
    
    bot.send_message(GROUP_ID, "⏳ <b>AUTO-START in 3 MINUTES!</b> Hop in now, bro☠️", parse_mode="HTML")
    
    # Ito yung timer na maghihintay ng 3 minutes (180 seconds) bago mag-start ang 10-1 countdown
    # Ginamit natin ang 'daemon=True' para sigurado na hindi mag-iiwan ng "zombie threads"
    t = threading.Timer(180.0, run_countdown_sequence)
    t.daemon = True 
    t.start()

def run_countdown_sequence():
    global game_state
    
    # 1. 10 down to 1 (Countdown)
    for i in range(10, 0, -1):
        # Sa bawat step, iche-check natin kung cancelled na ba ang game
        if not game_state.get("active") or game_state.get("phase") != "joining": 
            return
            
        try:
            bot.send_message(GROUP_ID, f"🚨 <b>Match starting in... {i}</b>", parse_mode="HTML")
        except:
            # Dito natin hinahawakan kung magka-error man ang telegram
            pass
            
        time.sleep(1) # Hinto ng 1 second bago mag-send ulit
        
    # 2. Confirmation Phase
    if not game_state.get("active") or game_state.get("phase") != "joining": 
        return
        
    bot.send_message(GROUP_ID, "⚠️ <b>Last call!</b> No more players joining? We’re starting now...", parse_mode="HTML")
    time.sleep(3) # 3 seconds buffer para sa final reactions
    
    # 3. Silent/Quick Countdown 3 to 1
    for i in range(3, 0, -1):
        if not game_state.get("active") or game_state.get("phase") != "joining": 
            return
        try:
            bot.send_message(GROUP_ID, f"🔥 <b>{i}</b>", parse_mode="HTML")
        except:
            pass
        time.sleep(0.8) # Bahagyang mas mabilis
        
    # 4. Start Game
    # Siguraduhin na 'joining' pa rin ang phase bago i-start ang game
    if game_state.get("active") and game_state.get("phase") == "joining":
        start_game(None)

def update_join_message():
    global game_state
    if not game_state["active"]: return
    
    is_group_game = game_state["name"].lower() in ["time bomb", "triple luck"]
    markup = InlineKeyboardMarkup()
    
    count = 0
    if is_group_game:
        markup.add(InlineKeyboardButton(f"🟢 GROUP GREEN ({len(game_state['groups']['Green'])}/4)", callback_data="join_grp_Green"),
                   InlineKeyboardButton(f"🔵 GROUP BLUE ({len(game_state['groups']['Blue'])}/4)", callback_data="join_grp_Blue"))
        markup.add(InlineKeyboardButton(f"🔴 GROUP RED ({len(game_state['groups']['Red'])}/4)", callback_data="join_grp_Red"),
                   InlineKeyboardButton(f"🟡 GROUP YELLOW ({len(game_state['groups']['Yellow'])}/4)", callback_data="join_grp_Yellow"))
        count = sum(len(g) for g in game_state["groups"].values())
    else:
        markup.add(InlineKeyboardButton(f"🎮 JOIN TOURNAMENT ({len(game_state['players'])})", callback_data="join_1v1"))
        count = len(game_state["players"])
        
    markup.add(InlineKeyboardButton("▶️ START GAME NOW", callback_data="start_game_btn"))
    
    desc = GAME_DESCRIPTIONS.get(game_state["name"], "Enjoy the hardcore tournament, bro!")
    text = f"🔥 <b>NEW TOURNAMENT STARTED</b> 🔥\nGame: {game_state['name'].upper()}\nPrize: {game_state['prize_count']}x {game_state['prize_cat']}\n\n📖 <b>Rules:</b> {desc}\n\n👥 <b>Total Players Joined:</b> {count}\nClick below to join bro!"
    try:
        bot.edit_message_text(text, GROUP_ID, game_state["msg_id"], reply_markup=markup, parse_mode="HTML")
    except:
        pass

@bot.message_handler(commands=['setgame'])
def setgame_cmd(message):
    if message.from_user.id not in ADMINS: return
    global game_state
    if game_state["active"]:
        bot.reply_to(message, "A game is already active bro!")
        return
        
    try:
        raw_text = message.text.replace("/setgame", "").strip()
        parts = raw_text.split("|")
        game_part = parts[0].strip() 
        cat_part = parts[1].strip()  
        
        bracket_index = game_part.find("[")
        game_name = game_part[:bracket_index].strip().replace("-", " ") # fixes tic-tac-toe
        count = int(game_part[bracket_index:].replace("[", "").replace("]", "").strip())
        
        game_state = {
            "active": True, "name": game_name.lower(), "prize_count": count, "prize_cat": cat_part,
            "phase": "joining", "players": [], "groups": {"Green": [], "Blue": [], "Red": [], "Yellow": []},
            "round": 0, "msg_id": None, "turn": None, "extra_data": {}, "timer_thread": None
        }
        
        msg = bot.send_message(GROUP_ID, "Loading tournament...", parse_mode="HTML")
        game_state["msg_id"] = msg.message_id
        update_join_message()
        
        # Start auto countdown
        threading.Thread(target=auto_start_countdown).start()
        
    except Exception as e:
        bot.reply_to(message, "⚠️ <b>Wrong format bro!</b>\nUse: <code>/setgame Game Name [Qty] | Category</code>\nExample: <code>/setgame Tic-Tac-Toe [1] | CPM2 Regular</code>", parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data.startswith("join_"))
def join_game(call):
    global game_state
    if not game_state["active"] or game_state["phase"] != "joining":
        bot.answer_callback_query(call.id, "Game already started or ended bro!", show_alert=True)
        return
        
    user = {"id": call.from_user.id, "username": call.from_user.username or call.from_user.first_name}
    
    if call.data == "join_1v1":
        if any(p['id'] == user['id'] for p in game_state["players"]):
            bot.answer_callback_query(call.id, "You already joined bro!")
        else:
            game_state["players"].append(user)
            bot.answer_callback_query(call.id, "Joined successfully bro!")
            update_join_message()
            
    elif call.data.startswith("join_grp_"):
        color = call.data.split("_")[2]
        if len(game_state["groups"][color]) >= 4:
            bot.answer_callback_query(call.id, "MAX PLAYER PER GROUP IS 4! Full is bro.", show_alert=True)
            return
            
        for c in game_state["groups"]:
            game_state["groups"][c] = [p for p in game_state["groups"][c] if p['id'] != user['id']]
        
        game_state["groups"][color].append(user)
        bot.answer_callback_query(call.id, f"Joined Group {color} bro!")
        update_join_message()

@bot.callback_query_handler(func=lambda call: call.data == "start_game_btn")
def start_btn_handler(call):
    if call.from_user.id not in ADMINS:
        bot.answer_callback_query(call.id, "Only admins can start bro!", show_alert=True)
        return
    start_game(call)

def start_game(call):
    global game_state
    game_state["phase"] = "playing"
    game_state["round"] = 1
    
    try: bot.delete_message(GROUP_ID, game_state["msg_id"])
    except: pass
        
    gn = game_state["name"]
    if gn == "time bomb": start_time_bomb()
    elif gn == "russian roulette": start_russian_roulette()
    elif gn == "rps showdown": start_rps_showdown()
    elif gn == "reaction test": start_reaction_test()
    elif gn == "lucky dice": start_lucky_dice()
    elif gn == "chat assassin": start_chat_assassin()
    elif gn == "math prodigy": start_math_prodigy()
    elif gn == "treasure hunt": start_treasure_hunt()
    elif gn == "triple luck": start_triple_luck()
    elif gn == "tic tac toe": start_tic_tac_toe()
    else:
        bot.send_message(GROUP_ID, "Bro, this game module is not found, skipping logic!")
        game_state["active"] = False

# ==========================================
# 🎮 GAME 1: TIME BOMB (Group, 10s Timer, No pass back)
# ==========================================
def tb_timeout():
    global game_state
    if not game_state["active"] or game_state["phase"] != "playing": return
    
    eliminated_color = game_state["extra_data"]["reps"][game_state["extra_data"]["bomb_idx"]]["color"]
    game_state["groups"][eliminated_color] = [] 
    
    try: bot.delete_message(GROUP_ID, game_state["msg_id"]) 
    except: pass
    bot.send_message(GROUP_ID, f"💥 KABOOM! Running out of time! Eliminated group {eliminated_color} bro!")
    
    alive_groups = {c: p for c, p in game_state["groups"].items() if len(p) > 0}
    if len(alive_groups) == 1:
        winner_color = list(alive_groups.keys())[0]
        winners = alive_groups[winner_color]
        bot.send_message(GROUP_ID, f"🏆 GROUP {winner_color.upper()} WINS! Distributing accounts...")
        distribute_prize(winners)
        game_state["active"] = False
    else:
        game_state["round"] += 1
        time.sleep(3)
        start_time_bomb()

def start_time_bomb():
    global game_state
    alive_groups = {c: p for c, p in game_state["groups"].items() if len(p) > 0}
    if len(alive_groups) < 2:
        bot.send_message(GROUP_ID, "Not enough groups joined bro! Cancelled.")
        game_state["active"] = False
        return
        
    reps = [{"color": c, "player": random.choice(players)} for c, players in alive_groups.items()]
    
    # ensure bomb is passed to valid target
    if "bomb_idx" not in game_state["extra_data"]:
        game_state["extra_data"]["bomb_idx"] = random.randint(0, len(reps)-1)
        game_state["extra_data"]["last_holder"] = -1
        
    game_state["extra_data"]["reps"] = reps
    send_bomb_ui()

def send_bomb_ui():
    global game_state
    cancel_timer()
    
    reps = game_state["extra_data"]["reps"]
    b_idx = game_state["extra_data"]["bomb_idx"]
    last_holder = game_state["extra_data"].get("last_holder", -1)
    holder = reps[b_idx]["player"]
    
    markup = InlineKeyboardMarkup(row_width=2)
    buttons = []
    alive_text = ""
    for i, rep in enumerate(reps):
        c_emoji = {"Green":"🟢", "Blue":"🔵", "Red":"🔴", "Yellow":"🟡"}[rep["color"]]
        alive_text += f"{c_emoji} @{rep['player']['username']} | "
        if i != b_idx and i != last_holder:
            buttons.append(InlineKeyboardButton(f"{c_emoji} Pass to @{rep['player']['username']}", callback_data=f"bomb_pass_{i}"))
            
    markup.add(*buttons)
    text = f"╔════════════════════════╗\n💣 <b>TIME BOMB — ROUND {game_state['round']}</b>\n╚════════════════════════╝\n🏃‍♂️ ALIVE PLAYERS:\n{alive_text}\n\n⚠️ 🚨 THE BOMB IS TICKING:\n💣 [ @{holder['username']} ] has the bomb!!!\n\n💥 FUSE TIMER: 10s remaining!\n[████████░░░░]\n──────────────────────\n👇 @{holder['username']}, PASS THE BOMB INSTANTLY!"
    
    if game_state["msg_id"]:
        try: bot.delete_message(GROUP_ID, game_state["msg_id"])
        except: pass
        
    msg = bot.send_message(GROUP_ID, text, reply_markup=markup, parse_mode="HTML")
    game_state["msg_id"] = msg.message_id
    game_state["turn"] = holder['id']
    
    t = threading.Timer(11.0, tb_timeout)
    t.start()
    game_state["timer_thread"] = t

@bot.callback_query_handler(func=lambda call: call.data.startswith("bomb_pass_"))
def bomb_handler(call):
    global game_state
    if call.from_user.id != game_state["turn"]:
        bot.answer_callback_query(call.id, "DON'T CHEAT MY BRO BRO 💀👀", show_alert=True)
        return
        
    cancel_timer()
    target_idx = int(call.data.split("_")[2])
    bot.answer_callback_query(call.id, "Bomb passed! Phew! 💦")
    
    game_state["extra_data"]["last_holder"] = game_state["extra_data"]["bomb_idx"]
    game_state["extra_data"]["bomb_idx"] = target_idx
    send_bomb_ui()

# ==========================================
# 🎮 GAME 2: RUSSIAN ROULETTE (Fixed Syntax & Bonus Round)
# ==========================================
def rr_timeout():
    global game_state
    if not game_state["active"] or game_state["phase"] != "playing": return
    
    # KUNG BONUS ROUND TIMEOUT
    if game_state["extra_data"].get("is_bonus_round"):
        pulled = game_state["extra_data"].get("bonus_pulled", {})
        p1 = game_state["extra_data"]["bonus_p1"]
        p2 = game_state["extra_data"]["bonus_p2"]
        
        dead_players = [p for p in [p1, p2] if p['id'] not in pulled]
        for dp in dead_players:
            game_state["players"] = [p for p in game_state["players"] if p['id'] != dp['id']]
            bot.send_message(GROUP_ID, f"⏰ Time's up! @{dp['username']} was kicked for not pulling the trigger!")
            
        try:
            bot.delete_message(GROUP_ID, game_state["msg_id"])
        except:
            pass
        
        if len(game_state["players"]) <= 1:
            if len(game_state["players"]) == 1:
                bot.send_message(GROUP_ID, f"🏆 @{game_state['players'][0]['username']} SURVIVED AND WON!")
                distribute_prize(game_state["players"])
            game_state["active"] = False
        else:
            game_state["round"] += 1
            start_rr_countdown(5)
        return

    # KUNG NORMAL ROUND TIMEOUT
    curr_idx = game_state["extra_data"]["current_idx"]
    dead = game_state["extra_data"]["rr_players"][curr_idx]
    
    game_state["players"] = [p for p in game_state["players"] if p['id'] != dead['id']]
    try:
        bot.delete_message(GROUP_ID, game_state["msg_id"])
    except:
        pass
    bot.send_message(GROUP_ID, f"⏰ Time's up! @{dead['username']} was kicked for not pulling the trigger!")
    
    if len(game_state["players"]) == 1:
        bot.send_message(GROUP_ID, f"🏆 @{game_state['players'][0]['username']} SURVIVED AND WON!")
        distribute_prize(game_state["players"])
        game_state["active"] = False
    else:
        game_state["round"] += 1
        time.sleep(2)
        start_russian_roulette()

def start_russian_roulette():
    global game_state
    if len(game_state["players"]) < 2:
        game_state["active"] = False; return
        
    if game_state["round"] > 0 and game_state["round"] % 4 == 0 and len(game_state["players"]) >= 2:
        start_bonus_round()
        return

    current_players = game_state["players"][:4]
    game_state["extra_data"]["bullet"] = random.randint(1, 6)
    game_state["extra_data"]["chamber"] = 1
    game_state["extra_data"]["rr_players"] = current_players
    game_state["extra_data"]["current_idx"] = 0
    game_state["extra_data"]["spun"] = False
    game_state["extra_data"]["is_bonus_round"] = False
    game_state["extra_data"]["resolved"] = False
    send_rr_ui()

def send_rr_ui():
    global game_state
    try:
        cancel_timer()
    except:
        pass
    
    rr_players = game_state["extra_data"]["rr_players"]
    curr_idx = game_state["extra_data"]["current_idx"]
    turn_player = rr_players[curr_idx]
    
    markup = InlineKeyboardMarkup()
    if not game_state["extra_data"].get("spun"):
        markup.add(InlineKeyboardButton("🔄 SPIN THE CHAMBER", callback_data=f"rr_spin_{turn_player['id']}"))
    markup.add(InlineKeyboardButton("🔫 PULL THE TRIGGER", callback_data=f"rr_pull_{turn_player['id']}"))
    
    next_players = " ➔ ".join([f"@{p['username']}" for i, p in enumerate(rr_players) if i != curr_idx])
    text = f"┏━━━━━━━━━━━━━━━━━━━━━━━━┓\n🔫 <b>RUSSIAN ROULETTE — ROUND {game_state['round']}</b>\n┗━━━━━━━━━━━━━━━━━━━━━━━━┛\n💀 CHAMBER STATUS: \n1 Bullet, {6 - game_state['extra_data']['chamber']} Empty Spaces\n\n🔄 CURRENT TURN: \n🟢 @{turn_player['username']}'s turn!\n⏳ Timer: 15 seconds!\n\n👥 NEXT IN LINE:\n{next_players}\n──────────────────────\n👇 @{turn_player['username']}, face your luck and pull the trigger!"
    
    if game_state.get("msg_id"):
        try:
            bot.delete_message(GROUP_ID, game_state["msg_id"])
        except:
            pass
        
    msg = bot.send_message(GROUP_ID, text, reply_markup=markup, parse_mode="HTML")
    game_state["msg_id"] = msg.message_id
    game_state["turn"] = turn_player['id']
    
    t = threading.Timer(15.0, rr_timeout)
    t.start()
    game_state["timer_thread"] = t

@bot.callback_query_handler(func=lambda call: call.data.startswith("rr_spin_"))
def rr_spin_handler(call):
    global game_state
    if not game_state["active"] or game_state["extra_data"].get("is_bonus_round"): return
    
    if call.from_user.id != game_state["turn"]:
        bot.answer_callback_query(call.id, "DON'T CHEAT MY BRO BRO 💀👀", show_alert=True); return
        
    if game_state["extra_data"].get("spun"):
        bot.answer_callback_query(call.id, "You already spun bro!", show_alert=True); return
        
    game_state["extra_data"]["spun"] = True
    game_state["extra_data"]["bullet"] = random.randint(1, 6)
    game_state["extra_data"]["chamber"] = 1
    
    bot.answer_callback_query(call.id, "🔥☠️YOUR CHAMBER IS READY TO FIRE🔥☠️", show_alert=True)
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔫 PULL THE TRIGGER", callback_data=f"rr_pull_{game_state['turn']}"))
    try:
        bot.edit_message_reply_markup(GROUP_ID, game_state["msg_id"], reply_markup=markup)
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data.startswith("rr_pull_"))
def rr_handler(call):
    global game_state
    if call.from_user.id != game_state["turn"]:
        bot.answer_callback_query(call.id, "DON'T CHEAT MY BRO BRO 💀👀", show_alert=True); return
        
    if game_state["extra_data"].get("resolved", False):
        bot.answer_callback_query(call.id, "Processing bro...", show_alert=False); return
        
    game_state["extra_data"]["resolved"] = True
    try:
        cancel_timer()
    except:
        pass
    
    bullet = game_state["extra_data"]["bullet"]
    chamber = game_state["extra_data"]["chamber"]
    rr_players = game_state["extra_data"]["rr_players"]
    curr_idx = game_state["extra_data"]["current_idx"]
    
    if chamber == bullet:
        dead = rr_players[curr_idx]
        bot.answer_callback_query(call.id, "💥 BANG! You're dead bro!", show_alert=True)
        game_state["players"] = [p for p in game_state["players"] if p['id'] != dead['id']]
        
        try:
            bot.delete_message(GROUP_ID, game_state["msg_id"])
        except:
            pass
        bot.send_message(GROUP_ID, f"💥 BANG! @{dead['username']} was eliminated!")
        
        if len(game_state["players"]) == 1:
            bot.send_message(GROUP_ID, f"🏆 @{game_state['players'][0]['username']} SURVIVED AND WON!")
            distribute_prize(game_state["players"])
            game_state["active"] = False
        else:
            game_state["round"] += 1
            time.sleep(2)
            start_russian_roulette()
    else:
        bot.answer_callback_query(call.id, "Click! You survived this round bro!")
        game_state["extra_data"]["chamber"] += 1
        game_state["extra_data"]["current_idx"] = (curr_idx + 1) % len(rr_players)
        game_state["extra_data"]["spun"] = False
        game_state["extra_data"]["resolved"] = False
        send_rr_ui()

def start_bonus_round():
    global game_state
    game_state["extra_data"]["is_bonus_round"] = True
    game_state["extra_data"]["bonus_pulled"] = {}
    
    p1, p2 = game_state["players"][0], game_state["players"][1]
    game_state["extra_data"]["bonus_p1"] = p1
    game_state["extra_data"]["bonus_p2"] = p2
    game_state["extra_data"]["bonus_loser"] = random.choice([p1['id'], p2['id']])
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔫 PULL THE TRIGGER", callback_data="rr_bonus_pull"))
    
    text = (
        "☠️<b>BONUS ROUND BRO BRO</b> 😈☠️\n\n"
        "💀☠️TWO PLAYER, ONE GUN EACH, BUT OTHER GUN IS EMPTY AND THE OTHER GUN IS LOADED WITH AMMO💀☠️\n\n"
        "☠️👿 GOOD LUCK BRO BRO 😈💀\n"
        f"@{p1['username']} 🆚 @{p2['username']}"
    )
    
    try:
        bot.delete_message(GROUP_ID, game_state.get("msg_id"))
    except:
        pass
    msg = bot.send_message(GROUP_ID, text, reply_markup=markup, parse_mode="HTML")
    game_state["msg_id"] = msg.message_id
    
    t = threading.Timer(20.0, rr_timeout)
    t.start()
    game_state["timer_thread"] = t

@bot.callback_query_handler(func=lambda call: call.data == "rr_bonus_pull")
def rr_bonus_pull_handler(call):
    global game_state
    if not game_state["active"] or not game_state["extra_data"].get("is_bonus_round"): return
    
    user_id = call.from_user.id
    p1 = game_state["extra_data"]["bonus_p1"]
    p2 = game_state["extra_data"]["bonus_p2"]
    
    if user_id not in [p1['id'], p2['id']]:
        bot.answer_callback_query(call.id, "DON'T CHEAT MY BRO BRO 💀👀", show_alert=True); return
        
    if user_id in game_state["extra_data"]["bonus_pulled"]:
        bot.answer_callback_query(call.id, "You already pulled the trigger bro!", show_alert=True); return
        
    game_state["extra_data"]["bonus_pulled"][user_id] = True
    bot.answer_callback_query(call.id, "You pulled the trigger... waiting for result!")
    
    if len(game_state["extra_data"]["bonus_pulled"]) == 2:
        resolve_bonus_round()
    else:
        pulled_player = p1 if user_id == p1['id'] else p2
        other_player = p2 if user_id == p1['id'] else p1
        bot.send_message(GROUP_ID, f"This @{pulled_player['username']} is already pull he's trigger, waiting for you Mr.@{other_player['username']} haha 👿")

def resolve_bonus_round():
    global game_state
    try:
        cancel_timer()
    except:
        pass
    
    loser_id = game_state["extra_data"]["bonus_loser"]
    p1 = game_state["extra_data"]["bonus_p1"]
    p2 = game_state["extra_data"]["bonus_p2"]
    
    loser = p1 if loser_id == p1['id'] else p2
    winner = p2 if loser_id == p1['id'] else p1
    
    msg_text = (
        f"💥 <b>BANG!</b> The smoke clears...\n\n"
        f"💀 @{loser['username']}'s gun was loaded!\n"
        f"🟢 @{winner['username']} survived!"
    )
    
    try:
        bot.delete_message(GROUP_ID, game_state["msg_id"])
    except:
        pass
    bot.send_message(GROUP_ID, msg_text, parse_mode="HTML")
    
    game_state["players"] = [p for p in game_state["players"] if p['id'] != loser_id]
    
    if len(game_state["players"]) == 1:
        bot.send_message(GROUP_ID, f"🏆 @{game_state['players'][0]['username']} SURVIVED AND WON!")
        try:
            distribute_prize(game_state["players"])
        except:
            pass
        game_state["active"] = False
    else:
        game_state["round"] += 1
        start_rr_countdown(5, None)

def start_rr_countdown(count, msg_id=None):
    global game_state
    if not game_state["active"]: return
    
    if msg_id is None:
        msg = bot.send_message(GROUP_ID, "⏳ <b>Next round in... 5</b>", parse_mode="HTML")
        threading.Timer(1.0, start_rr_countdown, args=[4, msg.message_id]).start()
    elif count > 0:
        try:
            bot.edit_message_text(f"⏳ <b>Next round in... {count}</b>", GROUP_ID, msg_id, parse_mode="HTML")
        except:
            pass
        threading.Timer(1.0, start_rr_countdown, args=[count-1, msg_id]).start()
    else:
        try:
            bot.delete_message(GROUP_ID, msg_id)
        except:
            pass
        start_russian_roulette()
        
# ==========================================
# 🎮 GAME 3: RPS SHOWDOWN (Locked Answers)
# ==========================================
def start_rps_showdown():
    global game_state
    if len(game_state["players"]) < 2:
        bot.send_message(GROUP_ID, "Not enough players bro! Cancelled.")
        game_state["active"] = False; return
    p1 = game_state["players"][0]
    p2 = game_state["players"][1]
    
    markup = InlineKeyboardMarkup(row_width=3)
    markup.add(
        InlineKeyboardButton("ROCK 🤘", callback_data="rps_rock"),
        InlineKeyboardButton("PAPER 📄", callback_data="rps_paper"),
        InlineKeyboardButton("SCISSORS ✂", callback_data="rps_scissors")
    )
    
    waiting = " ".join([f"@{p['username']}" for p in game_state["players"][2:]])
    text = f"⚔️ <b>RPS SHOWDOWN - ROUND {game_state['round']}</b> ⚔️\n\n👥 Waiting:\n{waiting if waiting else 'None'}\n\n🥊 CURRENT MATCH:\n@{p1['username']} 🆚 @{p2['username']}\n───────────────────────\nPick your weapon below!"
    
    if game_state["msg_id"]:
        try: bot.delete_message(GROUP_ID, game_state["msg_id"])
        except: pass
        
    msg = bot.send_message(GROUP_ID, text, reply_markup=markup, parse_mode="HTML")
    game_state["msg_id"] = msg.message_id
    game_state["turn"] = [p1['id'], p2['id']]
    game_state["extra_data"] = {"choices": {}}

@bot.callback_query_handler(func=lambda call: call.data.startswith("rps_"))
def rps_handler(call):
    global game_state
    if call.from_user.id not in game_state["turn"]:
        bot.answer_callback_query(call.id, "DON'T CHEAT MY BRO BRO 💀👀", show_alert=True)
        return
        
    # LOCK SYSTEM
    if call.from_user.id in game_state["extra_data"]["choices"]:
        bot.answer_callback_query(call.id, "You already locked your answer bro!", show_alert=True)
        return
        
    choice = call.data.split("_")[1]
    game_state["extra_data"]["choices"][call.from_user.id] = choice
    bot.answer_callback_query(call.id, f"You locked in {choice.upper()}!")
    
    if len(game_state["extra_data"]["choices"]) == 2:
        resolve_rps()

def resolve_rps():
    global game_state
    p1 = game_state["players"][0]
    p2 = game_state["players"][1]
    c1 = game_state["extra_data"]["choices"][p1['id']]
    c2 = game_state["extra_data"]["choices"][p2['id']]
    win_map = {"rock": "scissors", "paper": "rock", "scissors": "paper"}
    
    try: bot.delete_message(GROUP_ID, game_state["msg_id"])
    except: pass
    
    if c1 == c2:
        bot.send_message(GROUP_ID, f"DRAW! Both picked {c1.upper()}. Going to next round!")
        start_rps_showdown()
        return
        
    loser = p2 if win_map[c1] == c2 else p1
    winner = p1 if win_map[c1] == c2 else p2
    
    game_state["players"] = [p for p in game_state["players"] if p['id'] != loser['id']]
    bot.send_message(GROUP_ID, f"@{p1['username']} = {c1.upper()}\n🆚\n@{p2['username']} = {c2.upper()}\n\nLOST 🤣 : @{loser['username']}", parse_mode="HTML")
    
    if len(game_state["players"]) == 1:
        bot.send_message(GROUP_ID, f"🏆 @{winner['username']} IS THE RPS GRAND CHAMPION!")
        distribute_prize(game_state["players"])
        game_state["active"] = False
    else:
        game_state["round"] += 1
        time.sleep(2)
        start_rps_showdown()

# ==========================================
# 🎮 GAME 4: REACTION TEST 
# ==========================================
def start_reaction_test():
    global game_state
    if len(game_state["players"]) == 0:
        game_state["active"] = False; return
        
    bot.send_message(GROUP_ID, "⚡ <b>REACTION TEST</b> ⚡\nKeep your eyes on the chat! The button will appear soon...", parse_mode="HTML")
    time.sleep(random.uniform(3, 7))
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("⚡ CLICK FAST! ⚡", callback_data="react_btn"))
    msg = bot.send_message(GROUP_ID, "👇 CLICK NOW!!! 👇", reply_markup=markup)
    
    game_state["msg_id"] = msg.message_id
    game_state["phase"] = "reacting"

@bot.callback_query_handler(func=lambda call: call.data == "react_btn")
def react_handler(call):
    global game_state
    if game_state["phase"] != "reacting": return
    if not any(p['id'] == call.from_user.id for p in game_state["players"]):
        bot.answer_callback_query(call.id, "You didn't join the game bro!")
        return
    
    game_state["phase"] = "ended"
    try: bot.delete_message(GROUP_ID, game_state["msg_id"])
    except: pass
    
    winner = next(p for p in game_state["players"] if p['id'] == call.from_user.id)
    bot.send_message(GROUP_ID, f"⚡ <b>FASTEST HANDS!</b>\n@{winner['username']} clicked it first and wins the match!", parse_mode="HTML")
    distribute_prize([winner])
    game_state["active"] = False

# ==========================================
# 🎮 GAME 5: LUCKY DICE (Fixed Rate-Limit Issue)
# ==========================================
def start_lucky_dice():
    global game_state
    if len(game_state["players"]) < 2:
        bot.send_message(GROUP_ID, "Need at least 2 players bro! Cancelled."); game_state["active"] = False; return
        
    game_state["extra_data"]["rolls"] = {}
    game_state["extra_data"]["round_active"] = True
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🎲 ROLL DICE", callback_data="ld_roll"))
    
    # 🟢 BINALIK NATIN YUNG LISTAHAN DITO (Static List para iwas lag)
    player_list = " | ".join([f"@{p['username']}" for p in game_state["players"]])
    
    text = (
        f"🎲 <b>LUCKY DICE - Round {game_state['round']}</b>\n"
        f"───────────────────────\n"
        f"👥 <b>PLAYERS ALIVE:</b>\n{player_list}\n\n"
        f"⏱️ <b>Timer: 25 Seconds!</b>\n\n"
        f"👇 Click the button below to roll!\n"
        f"(Lowest roll gets eliminated!)"
    )
    
    if game_state.get("msg_id"):
        try: bot.delete_message(GROUP_ID, game_state["msg_id"])
        except: pass
        
    msg = bot.send_message(GROUP_ID, text, reply_markup=markup, parse_mode="HTML")
    game_state["msg_id"] = msg.message_id
    
    # Simulan ang 25-second background timer para sa round na ito
    current_round = game_state['round']
    t = threading.Timer(25.0, lucky_dice_timeout, args=[current_round])
    game_state["extra_data"]["timer"] = t
    t.start()

def lucky_dice_timeout(round_num):
    global game_state
    # Proteksyon para hindi mag-trigger kung tapos na ang round o iba na ang laro
    if not game_state["active"] or game_state["round"] != round_num:
        return
    if not game_state["extra_data"].get("round_active"):
        return
        
    bot.send_message(GROUP_ID, "⏰ <b>Time's up!</b> Processing players who failed to roll...", parse_mode="HTML")
    resolve_lucky_dice()

@bot.callback_query_handler(func=lambda call: call.data == "ld_roll")
def ld_handler(call):
    global game_state
    if not game_state["active"] or not game_state["extra_data"].get("round_active"):
        bot.answer_callback_query(call.id, "No active round bro!", show_alert=True); return
        
    player_id = call.from_user.id
    if not any(p['id'] == player_id for p in game_state["players"]):
        bot.answer_callback_query(call.id, "DON'T CHEAT MY BRO BRO 💀👀", show_alert=True); return
        
    if player_id in game_state["extra_data"]["rolls"]:
        bot.answer_callback_query(call.id, "DON'T CHEAT MY BRO BRO 💀👀 (You already rolled!)", show_alert=True); return
        
    roll = random.randint(1, 100)
    game_state["extra_data"]["rolls"][player_id] = roll
    
    # Dito makikita ng player yung roll nila via pop-up alert
    bot.answer_callback_query(call.id, f"🎲 You rolled a {roll}!", show_alert=True)
    
    # Kung nakapag-roll na ang lahat bago mag-25 seconds
    if len(game_state["extra_data"]["rolls"]) == len(game_state["players"]):
        if "timer" in game_state["extra_data"]:
            try: game_state["extra_data"]["timer"].cancel()
            except: pass
        resolve_lucky_dice()
        
    # 🛑 INALIS NA NATIN YUNG ELSE BLOCK NA MAY EDIT_MESSAGE_TEXT DITO 🛑

def resolve_lucky_dice():
    global game_state
    if not game_state["extra_data"].get("round_active"):
        return
    game_state["extra_data"]["round_active"] = False  # Lock para iwas double trigger
    
    if "timer" in game_state["extra_data"]:
        try: game_state["extra_data"]["timer"].cancel()
        except: pass
        
    rolls = game_state["extra_data"]["rolls"]
    
    # Kung may hindi nakapag-roll pagka-timeout, automatic 0 score sila
    for p in game_state["players"]:
        if p['id'] not in rolls:
            rolls[p['id']] = 0
            
    lowest_id = min(rolls, key=rolls.get)
    lowest_player = next(p for p in game_state["players"] if p['id'] == lowest_id)
    
    text = f"🎲 <b>LUCKY DICE RESULTS - Round {game_state['round']}</b> 🎲\n───────────────────────\n"
    for p in game_state["players"]:
        score = rolls[p['id']]
        score_text = f"<b>{score}</b>" if score > 0 else "❌ <i>Timed Out (0)</i>"
        text += f"@{p['username']} rolled: {score_text}\n"
        
    text += f"\n❌ <b>ELIMINATED:</b> @{lowest_player['username']} with score {rolls[lowest_id]}!"
    
    try: bot.delete_message(GROUP_ID, game_state["msg_id"])
    except: pass
    bot.send_message(GROUP_ID, text, parse_mode="HTML")
    
    game_state["players"] = [p for p in game_state["players"] if p['id'] != lowest_id]
    
    if len(game_state["players"]) == 1:
        bot.send_message(GROUP_ID, f"🏆 @{game_state['players'][0]['username']} WON THE LUCKY DICE! 🥇")
        
        # Paki-check lang na existing itong distribute_prize function sa bot mo
        try: distribute_prize(game_state["players"]) 
        except NameError: pass
        
        game_state["active"] = False
    elif len(game_state["players"]) == 0:
        bot.send_message(GROUP_ID, "⚠️ Everyone was eliminated! No winner this round.")
        game_state["active"] = False
    else:
        game_state["round"] += 1
        time.sleep(2)
        start_lucky_dice()

# ==========================================
# 🎮 GAME 6: CHAT ASSASSIN (2 Buttons, 10s Timer)
# ==========================================
def ca_timeout():
    global game_state
    if not game_state["active"] or game_state["phase"] != "playing": return
    p1 = game_state["players"][0]
    game_state["players"].pop(0)
    
    try: bot.delete_message(GROUP_ID, game_state["msg_id"])
    except: pass
    bot.send_message(GROUP_ID, f"⏰ Time's up! @{p1['username']} hesitated and was eliminated!")
    
    if len(game_state["players"]) == 1:
        bot.send_message(GROUP_ID, f"🏆 @{game_state['players'][0]['username']} IS THE MASTER ASSASSIN!")
        distribute_prize(game_state["players"])
        game_state["active"] = False
    else:
        game_state["round"] += 1
        time.sleep(2)
        start_chat_assassin()

def start_chat_assassin():
    global game_state
    if len(game_state["players"]) < 2:
        game_state["active"]=False; return
        
    p1 = game_state["players"][0]
    p2 = game_state["players"][1]
    
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("🩸 ASSASSINATE 🩸", callback_data="ca_kill"))
    markup.add(InlineKeyboardButton("NAH I DON'T WANT TO ASSASSINATE THIS GUY", callback_data="ca_spare"))
    
    msg = bot.send_message(GROUP_ID, f"🥷 <b>CHAT ASSASSIN - Round {game_state['round']}</b>\n\n🎯 Target: @{p2['username']}\n🔪 Assassin: @{p1['username']}\n\n@{p1['username']}, you have 10 seconds to decide! Strike or Spare?", reply_markup=markup, parse_mode="HTML")
    game_state["msg_id"] = msg.message_id
    game_state["turn"] = p1['id']
    
    t = threading.Timer(15.0, ca_timeout)
    t.start()
    game_state["timer_thread"] = t

@bot.callback_query_handler(func=lambda call: call.data.startswith("ca_"))
def assassin_handler(call):
    global game_state
    if call.from_user.id != game_state["turn"]:
        bot.answer_callback_query(call.id, "DON'T CHEAT MY BRO BRO 💀👀", show_alert=True); return
        
    cancel_timer()
    p1 = game_state["players"][0]
    p2 = game_state["players"][1]
    
    try: bot.delete_message(GROUP_ID, game_state["msg_id"])
    except: pass
    
    if call.data == "ca_kill":
        if random.random() > 0.5:
            bot.send_message(GROUP_ID, f"🩸 <b>SUCCESS!</b> @{p1['username']} assassinated @{p2['username']}!", parse_mode="HTML")
            game_state["players"].pop(1)
        else:
            bot.send_message(GROUP_ID, f"🛡️ <b>FAILED!</b> @{p2['username']} countered and killed @{p1['username']}!", parse_mode="HTML")
            game_state["players"].pop(0)
    else:
        if random.random() > 0.5:
            bot.send_message(GROUP_ID, f"🕊️ @{p1['username']} spared @{p2['username']} and SURVIVED to next round!", parse_mode="HTML")
            game_state["players"].append(game_state["players"].pop(0)) # cycle queue
        else:
            bot.send_message(GROUP_ID, f"💀 @{p1['username']} showed mercy, but @{p2['username']} stabbed them in the back! @{p1['username']} died!", parse_mode="HTML")
            game_state["players"].pop(0)
            
    if len(game_state["players"]) == 1:
        bot.send_message(GROUP_ID, f"🏆 @{game_state['players'][0]['username']} IS THE MASTER ASSASSIN!")
        distribute_prize(game_state["players"])
        game_state["active"] = False
    else:
        game_state["round"] += 1
        time.sleep(2)
        start_chat_assassin()

# ==========================================
# 🎮 GAME 7: MATH PRODIGY (Cars + Math)
# ==========================================
MIX_PRODIGY_QUESTIONS = [
    # Initial 45
    {
        "q_en": "A Skyline R34 runs 120 mph. You add nitro boosting it by 35 mph. New speed?", 
        "q_es": "Un Skyline R34 corre a 120 mph. Añades nitro que lo impulsa 35 mph. ¿Nueva velocidad?", 
        "q_ph": "Tumatakbo ng 120 mph ang Skyline R34. Nag-nitro ka ng 35 mph. Ano ang bagong speed?", 
        "a": "155"
    },
    {
        "q_en": "Supra mk4 has 320 HP. Upgrade turbo adding 400 HP. Total HP?", 
        "q_es": "Supra mk4 tiene 320 HP. Mejoras el turbo añadiendo 400 HP. ¿HP total?", 
        "q_ph": "May 320 HP ang Supra mk4. Nag-upgrade ka ng turbo na may 400 HP. Ilan ang total HP?", 
        "a": "720"
    },
    {
        "q_en": "You buy 4 CarX tires at 250 coins each. Total cost?", 
        "q_es": "Compras 4 llantas CarX a 250 monedas cada una. ¿Costo total?", 
        "q_ph": "Bumili ka ng 4 CarX tires sa halagang 250 coins bawat isa. Magkano lahat?", 
        "a": "1000"
    },
    {
        "q_en": "Engine needs 5 liters of oil, you have 2.5. How much more?", 
        "q_es": "El motor necesita 5 litros de aceite, tienes 2.5. ¿Cuánto más necesitas?", 
        "q_ph": "Kailangan ng makina ng 5 liters na langis, mayroon kang 2.5. Ilan pa ang kulang?", 
        "a": "2.5"
    },
    {
        "q_en": "15 x 6 ÷ 2 + 45", 
        "q_es": "15 x 6 ÷ 2 + 45", 
        "q_ph": "15 x 6 ÷ 2 + 45", 
        "a": "90"
    },
    {
        "q_en": "CPM2 car earns 50k a race. How much for 4 races?", 
        "q_es": "El coche CPM2 gana 50k por carrera. ¿Cuánto por 4 carreras?", 
        "q_ph": "Kumikita ang CPM2 car ng 50k kada race. Magkano sa 4 na races?", 
        "a": "200000"
    },
    {
        "q_en": "35 x 4 - (12 x 5)", 
        "q_es": "35 x 4 - (12 x 5)", 
        "q_ph": "35 x 4 - (12 x 5)", 
        "a": "80"
    },
    {
        "q_en": "GTR R35 costs 150k. You have 90k. How much more needed?", 
        "q_es": "GTR R35 cuesta 150k. Tienes 90k. ¿Cuánto más se necesita?", 
        "q_ph": "150k ang GTR R35. May 90k ka. Magkano pa ang kulang?", 
        "a": "60000"
    },
    {
        "q_en": "5⁴ - 500", 
        "q_es": "5⁴ - 500", 
        "q_ph": "5⁴ - 500", 
        "a": "125"
    },
    {
        "q_en": "Lap a track in 45 seconds. How many seconds for 3 laps?", 
        "q_es": "Das una vuelta en 45 segundos. ¿Cuántos segundos para 3 vueltas?", 
        "q_ph": "45 seconds ang isang lap. Ilang seconds para sa 3 laps?", 
        "a": "135"
    },
    {
        "q_en": "Drift gives 500 points per second. How many in 8 seconds?", 
        "q_es": "El derrape da 500 puntos por segundo. ¿Cuántos en 8 segundos?", 
        "q_ph": "Nagbibigay ng 500 points per second ang drift. Ilan sa 8 seconds?", 
        "a": "4000"
    },
    {
        "q_en": "(45 + 55) ÷ 5 x 4", 
        "q_es": "(45 + 55) ÷ 5 x 4", 
        "q_ph": "(45 + 55) ÷ 5 x 4", 
        "a": "80"
    },
    {
        "q_en": "Top speed 220. Brake reduces speed by 75. Current speed?", 
        "q_es": "Velocidad máxima 220. El freno reduce la velocidad en 75. ¿Velocidad actual?", 
        "q_ph": "Top speed ay 220. Nabawasan ng 75 dahil sa preno. Ano ang current speed?", 
        "a": "145"
    },
    {
        "q_en": "17 x 4 + 180 ÷ 6", 
        "q_es": "17 x 4 + 180 ÷ 6", 
        "q_ph": "17 x 4 + 180 ÷ 6", 
        "a": "98"
    },
    {
        "q_en": "Sell 3 engines for 800 each. Total profit?", 
        "q_es": "Vendes 3 motores por 800 cada uno. ¿Ganancia total?", 
        "q_ph": "Nagbenta ka ng 3 makina sa halagang 800 bawat isa. Magkano ang total na kinita?", 
        "a": "2400"
    },
    {
        "q_en": "2³ x 3³ - 100", 
        "q_es": "2³ x 3³ - 100", 
        "q_ph": "2³ x 3³ - 100", 
        "a": "116"
    },
    {
        "q_en": "Tuning a car costs 45k. You tune 2 cars. Total cost?", 
        "q_es": "Tunear un auto cuesta 45k. Tuneas 2 autos. ¿Costo total?", 
        "q_ph": "45k ang pag-tune ng kotse. Nag-tune ka ng 2 kotse. Magkano lahat?", 
        "a": "90000"
    },
    {
        "q_en": "11² + 12² - 100", 
        "q_es": "11² + 12² - 100", 
        "q_ph": "11² + 12² - 100", 
        "a": "165"
    },
    {
        "q_en": "Car weight 1200kg. You strip 150kg. New weight?", 
        "q_es": "El peso del auto es 1200kg. Le quitas 150kg. ¿Nuevo peso?", 
        "q_ph": "1200kg ang bigat ng kotse. Nagtanggal ka ng 150kg. Ano ang bagong bigat?", 
        "a": "1050"
    },
    {
        "q_en": "14 x 6 - (150 ÷ 3)", 
        "q_es": "14 x 6 - (150 ÷ 3)", 
        "q_ph": "14 x 6 - (150 ÷ 3)", 
        "a": "34"
    },
    {
        "q_en": "400m drag in 10s. Speed in m/s?", 
        "q_es": "Arrancones de 400m en 10s. ¿Velocidad en m/s?", 
        "q_ph": "400m drag race sa loob ng 10s. Ano ang speed in m/s?", 
        "a": "40"
    },
    {
        "q_en": "(50 + 75) ÷ 25 x 14", 
        "q_es": "(50 + 75) ÷ 25 x 14", 
        "q_ph": "(50 + 75) ÷ 25 x 14", 
        "a": "70"
    },
    {
        "q_en": "Turbo adds 20% HP to a 500 HP car. Total HP?", 
        "q_es": "El turbo añade un 20% de HP a un auto de 500 HP. ¿HP total?", 
        "q_ph": "Nagdagdag ng 20% HP ang turbo sa 500 HP na kotse. Ilan ang total HP?", 
        "a": "600"
    },
    {
        "q_en": "15² - (20 x 8)", 
        "q_es": "15² - (20 x 8)", 
        "q_ph": "15² - (20 x 8)", 
        "a": "65"
    },
    {
        "q_en": "Buy gas for 50 coins. You had 1000. Change?", 
        "q_es": "Compras gasolina por 50 monedas. Tenías 1000. ¿Cambio?", 
        "q_ph": "Bumili ka ng gas sa halagang 50 coins. Mayroon kang 1000. Magkano ang sukli?", 
        "a": "950"
    },
    {
        "q_en": "(16 x 4) + (18 x 3)", 
        "q_es": "(16 x 4) + (18 x 3)", 
        "q_ph": "(16 x 4) + (18 x 3)", 
        "a": "118"
    },
    {
        "q_en": "A wrap costs 1500. Buy 3 wraps. Total?", 
        "q_es": "Un vinilo (wrap) cuesta 1500. Compras 3. ¿Total?", 
        "q_ph": "1500 ang isang wrap. Bumili ka ng 3 wraps. Magkano lahat?", 
        "a": "4500"
    },
    {
        "q_en": "4³ + 5³ - 89", 
        "q_es": "4³ + 5³ - 89", 
        "q_ph": "4³ + 5³ - 89", 
        "a": "100"
    },
    {
        "q_en": "Car auction starts at 50k. Increase 5k 4 times. Final bid?", 
        "q_es": "La subasta de autos empieza en 50k. Sube 5k 4 veces. ¿Oferta final?", 
        "q_ph": "Nagsimula sa 50k ang car auction. Tumaas ng 5k ng 4 na beses. Magkano ang final bid?", 
        "a": "70000"
    },
    {
        "q_en": "13 x 7 - (108 ÷ 9)", 
        "q_es": "13 x 7 - (108 ÷ 9)", 
        "q_ph": "13 x 7 - (108 ÷ 9)", 
        "a": "79"
    },
    {
        "q_en": "1.5M coins minus 850k car. Remaining?", 
        "q_es": "1.5M monedas menos un auto de 850k. ¿Cuánto queda?", 
        "q_ph": "1.5M coins bawasan ng 850k na kotse. Magkano ang natira?", 
        "a": "650000"
    },
    {
        "q_en": "(25 x 4) + (50 x 3) - 100", 
        "q_es": "(25 x 4) + (50 x 3) - 100", 
        "q_ph": "(25 x 4) + (50 x 3) - 100", 
        "a": "150"
    },
    {
        "q_en": "0-100 in 3s. Seconds for 300km/h?", 
        "q_es": "0-100 en 3s. ¿Segundos para 300km/h?", 
        "q_ph": "0-100 sa loob ng 3s. Ilang seconds para sa 300km/h?", 
        "a": "9"
    },
    {
        "q_en": "Exhaust 50k, Turbo 100k, ECU 75k. Total upgrade cost?", 
        "q_es": "Escape 50k, Turbo 100k, ECU 75k. ¿Costo total de mejora?", 
        "q_ph": "Exhaust 50k, Turbo 100k, ECU 75k. Magkano ang total ng upgrade?", 
        "a": "225000"
    },
    {
        "q_en": "18 x 5 + (200 ÷ 4)", 
        "q_es": "18 x 5 + (200 ÷ 4)", 
        "q_ph": "18 x 5 + (200 ÷ 4)", 
        "a": "140"
    },
    {
        "q_en": "Trap at 250. Limit 180. How much over?", 
        "q_es": "Radar a 250. Límite 180. ¿Por cuánto te pasaste?", 
        "q_ph": "Na-trap sa 250. Ang limit ay 180. Ilan ang sobra?", 
        "a": "70"
    },
    {
        "q_en": "6³ - 16", 
        "q_es": "6³ - 16", 
        "q_ph": "6³ - 16", 
        "a": "200"
    },
    {
        "q_en": "2000 points per drift. 5 drifts. Total points?", 
        "q_es": "2000 puntos por derrape. 5 derrapes. ¿Puntos totales?", 
        "q_ph": "2000 points bawat drift. 5 drifts. Ilan ang total points?", 
        "a": "10000"
    },
    {
        "q_en": "9² + 8² - 45", 
        "q_es": "9² + 8² - 45", 
        "q_ph": "9² + 8² - 45", 
        "a": "100"
    },
    {
        "q_en": "Swap costs 300k. Earn 50k/mission. Missions needed?", 
        "q_es": "El cambio de motor cuesta 300k. Ganas 50k/misión. ¿Misiones necesarias?", 
        "q_ph": "300k ang engine swap. Kumikita ng 50k/mission. Ilang missions ang kailangan?", 
        "a": "6"
    },
    {
        "q_en": "(120 ÷ 6) + (15 x 7)", 
        "q_es": "(120 ÷ 6) + (15 x 7)", 
        "q_ph": "(120 ÷ 6) + (15 x 7)", 
        "a": "125"
    },
    {
        "q_en": "Garage holds 10. You own 3. Slots left?", 
        "q_es": "El garaje tiene espacio para 10. Tienes 3. ¿Espacios libres?", 
        "q_ph": "Kasya ang 10 sa garage. Mayroon kang 3. Ilang slots pa ang libre?", 
        "a": "7"
    },
    {
        "q_en": "10³ ÷ 10 + 50", 
        "q_es": "10³ ÷ 10 + 50", 
        "q_ph": "10³ ÷ 10 + 50", 
        "a": "150"
    },
    {
        "q_en": "(500 - 200) ÷ 3 + 10", 
        "q_es": "(500 - 200) ÷ 3 + 10", 
        "q_ph": "(500 - 200) ÷ 3 + 10", 
        "a": "110"
    },
    {
        "q_en": "9 x 9 + 19", 
        "q_es": "9 x 9 + 19", 
        "q_ph": "9 x 9 + 19", 
        "a": "100"
    },

    # Added 30
    {
        "q_en": "You have 1.5M coins. Bought car for 850k. Remaining?", 
        "q_es": "Tienes 1.5M monedas. Compraste un auto por 850k. ¿Cuánto queda?", 
        "q_ph": "Mayroon kang 1.5M coins. Bumili ng kotse sa halagang 850k. Magkano ang natira?", 
        "a": "650000"
    },
    {
        "q_en": "(25 x 4) + (50 x 3) - 100", 
        "q_es": "(25 x 4) + (50 x 3) - 100", 
        "q_ph": "(25 x 4) + (50 x 3) - 100", 
        "a": "150"
    },
    {
        "q_en": "0-100 in 3s. Seconds for 300km/h?", 
        "q_es": "0-100 en 3s. ¿Segundos para 300km/h?", 
        "q_ph": "0-100 sa loob ng 3s. Ilang seconds para sa 300km/h?", 
        "a": "9"
    },
    {
        "q_en": "Exhaust 50k, Turbo 100k, ECU 75k. Total upgrade?", 
        "q_es": "Escape 50k, Turbo 100k, ECU 75k. ¿Mejora total?", 
        "q_ph": "Exhaust 50k, Turbo 100k, ECU 75k. Magkano ang total upgrade?", 
        "a": "225000"
    },
    {
        "q_en": "18 x 5 + (200 ÷ 4)", 
        "q_es": "18 x 5 + (200 ÷ 4)", 
        "q_ph": "18 x 5 + (200 ÷ 4)", 
        "a": "140"
    },
    {
        "q_en": "Trap at 250. Limit 180. How much over?", 
        "q_es": "Radar a 250. Límite 180. ¿Por cuánto te pasaste?", 
        "q_ph": "Na-trap sa 250. Ang limit ay 180. Ilan ang sobra?", 
        "a": "70"
    },
    {
        "q_en": "6³ - 16", 
        "q_es": "6³ - 16", 
        "q_ph": "6³ - 16", 
        "a": "200"
    },
    {
        "q_en": "2000 points per drift. 5 drifts. Total points?", 
        "q_es": "2000 puntos por derrape. 5 derrapes. ¿Puntos totales?", 
        "q_ph": "2000 points bawat drift. 5 drifts. Ilan ang total points?", 
        "a": "10000"
    },
    {
        "q_en": "9² + 8² - 45", 
        "q_es": "9² + 8² - 45", 
        "q_ph": "9² + 8² - 45", 
        "a": "100"
    },
    {
        "q_en": "Swap 300k. Earn 50k/mission. How many missions?", 
        "q_es": "Cambio 300k. Ganas 50k/misión. ¿Cuántas misiones?", 
        "q_ph": "300k ang swap. Kumikita ng 50k/mission. Ilang missions?", 
        "a": "6"
    },
    {
        "q_en": "(120 ÷ 6) + (15 x 7)", 
        "q_es": "(120 ÷ 6) + (15 x 7)", 
        "q_ph": "(120 ÷ 6) + (15 x 7)", 
        "a": "125"
    },
    {
        "q_en": "Garage 10 slots. Own 3. Slots left?", 
        "q_es": "Garaje de 10 espacios. Tienes 3. ¿Espacios libres?", 
        "q_ph": "10 slots ang garage. Mayroon kang 3. Ilang slots pa ang libre?", 
        "a": "7"
    },
    {
        "q_en": "7 x 9 - (50 + 8)", 
        "q_es": "7 x 9 - (50 + 8)", 
        "q_ph": "7 x 9 - (50 + 8)", 
        "a": "5"
    },
    {
        "q_en": "Drive 15km in 10 mins. Km per minute?", 
        "q_es": "Manejas 15km en 10 min. ¿Km por minuto?", 
        "q_ph": "Nag-drive ka ng 15km sa loob ng 10 mins. Ilang km kada minuto?", 
        "a": "1.5"
    },
    {
        "q_en": "10³ ÷ 10 + 50", 
        "q_es": "10³ ÷ 10 + 50", 
        "q_ph": "10³ ÷ 10 + 50", 
        "a": "150"
    },
    {
        "q_en": "Wheel set 200. Buy 4. Total?", 
        "q_es": "Set de rines 200. Compras 4. ¿Total?", 
        "q_ph": "200 ang set ng gulong. Bumili ka ng 4. Magkano lahat?", 
        "a": "800"
    },
    {
        "q_en": "(500 - 200) ÷ 3 + 10", 
        "q_es": "(500 - 200) ÷ 3 + 10", 
        "q_ph": "(500 - 200) ÷ 3 + 10", 
        "a": "110"
    },
    {
        "q_en": "Gains 5 HP/level. HP gain for 12 levels?", 
        "q_es": "Gana 5 HP/nivel. ¿HP ganado en 12 niveles?", 
        "q_ph": "Nadadagdagan ng 5 HP/level. Ilan ang dagdag na HP para sa 12 levels?", 
        "a": "60"
    },
    {
        "q_en": "20 x 20 - (40 x 5)", 
        "q_es": "20 x 20 - (40 x 5)", 
        "q_ph": "20 x 20 - (40 x 5)", 
        "a": "200"
    },
    {
        "q_en": "The Race is 2 mins. How many seconds?", 
        "q_es": "Carrera de 2 min. ¿Cuántos segundos?", 
        "q_ph": "2 mins ang race. Ilang seconds 'yun?", 
        "a": "120"
    },
    {
        "q_en": "500k. Lose 20% in bet. How much left?", 
        "q_es": "Tienes 500k. Pierdes el 20% en una apuesta. ¿Cuánto queda?", 
        "q_ph": "May 500k ka. Natalo ang 20% sa pustahan. Magkano ang natira?", 
        "a": "400000"
    },
    {
        "q_en": "14² - 96", 
        "q_es": "14² - 96", 
        "q_ph": "14² - 96", 
        "a": "100"
    },
    {
        "q_en": "4 laps of 3km track. Total distance?", 
        "q_es": "4 vueltas en una pista de 3km. ¿Distancia total?", 
        "q_ph": "4 laps sa isang 3km na track. Ano ang total distance?", 
        "a": "12"
    },
    {
        "q_en": "Nitro 10s. 3 refills. Total duration?", 
        "q_es": "Nitro dura 10s. 3 recargas. ¿Duración total?", 
        "q_ph": "10s ang tagal ng nitro. 3 beses nag-refill. Ilang seconds lahat?", 
        "a": "30"
    },
    {
        "q_en": "(18 x 6) ÷ 4 + 7", 
        "q_es": "(18 x 6) ÷ 4 + 7", 
        "q_ph": "(18 x 6) ÷ 4 + 7", 
        "a": "34"
    },
    {
        "q_en": "Auction: Start 100k, +10k twice, +20k once. Final?", 
        "q_es": "Subasta: Inicia en 100k, +10k dos veces, +20k una vez. ¿Final?", 
        "q_ph": "Auction: Nagsimula sa 100k, +10k ng dalawang beses, +20k ng isang beses. Magkano lahat?", 
        "a": "140000"
    },
    {
        "q_en": "15 x 8 - (120 ÷ 2)", 
        "q_es": "15 x 8 - (120 ÷ 2)", 
        "q_ph": "15 x 8 - (120 ÷ 2)", 
        "a": "60"
    },
    {
        "q_en": "2.2M coins. Spend 400k. Remaining?", 
        "q_es": "2.2M monedas. Gastas 400k. ¿Cuánto queda?", 
        "q_ph": "2.2M coins. Gumastos ka ng 400k. Ilan ang natira?", 
        "a": "1800000"
    },
    {
        "q_en": "(9 x 9) + (19 x 1)", 
        "q_es": "(9 x 9) + (19 x 1)", 
        "q_ph": "(9 x 9) + (19 x 1)", 
        "a": "100"
    },
    {
        "q_en": "You have 500. Add 500. Total?", 
        "q_es": "Tienes 500. Añades 500. ¿Total?", 
        "q_ph": "Mayroon kang 500. Nagdagdag ng 500. Ilan ang total?", 
        "a": "1000"
    }
]

def cancel_timer():
    global game_state
    if "timer_thread" in game_state and game_state["timer_thread"]:
        game_state["timer_thread"].cancel()
        game_state["timer_thread"] = None

def start_math_prodigy():
    global game_state
    if not game_state.get("players"):
        game_state["active"] = False; return
        
    q_data = random.choice(MIX_PRODIGY_QUESTIONS)
    game_state["extra_data"]["math_ans"] = q_data["a"].replace(',', '').strip()
    game_state["phase"] = "math_waiting"
    
    # ITO YUNG BAGONG 3-LANGUAGE FORMAT BRO!
    text_msg = (
        "🧮 <b>MATH PRODIGY</b> 🧮\n"
        "First player to type the correct answer wins!\n"
        "───────────────────────\n"
        f"ENGLISH: ❓ {q_data['q_en']}\n"
        "───────────────────────\n"
        f"SPANISH: ❓ {q_data['q_es']}\n"
        "───────────────────────\n"
        f"FILIPINO: ❓ {q_data['q_ph']}\n"
        "───────────────────────\n"
        "⏳ <i>40 seconds timer!</i>\n"
        "───────────────────────"
    )
    
    msg = bot.send_message(GROUP_ID, text_msg, parse_mode="HTML")
    game_state["msg_id"] = msg.message_id
    
    # Timer: Auto-next logic
    t = threading.Timer(30.0, math_timeout)
    t.start()
    game_state["timer_thread"] = t

@bot.message_handler(func=lambda m: game_state.get("active") and game_state.get("phase") == "math_waiting" and m.chat.id == GROUP_ID)
def math_answer_handler(m):
    global game_state
    
    # ANTI DOUBLE-SEND BUG: I-check ulit dito kung waiting pa rin bago magpatuloy
    if game_state.get("phase") != "math_waiting":
        return
    
    # Filter: 200k -> 200000, 1,000 -> 1000
    user_ans = m.text.lower().replace('k', '000').replace(',', '').strip()
    correct_ans = game_state["extra_data"].get("math_ans", "").lower()
    
    if user_ans == correct_ans:
        # Check kung registered player
        if not any(p['id'] == m.from_user.id for p in game_state["players"]):
            bot.reply_to(m, "Correct, but you’re not in the tournament, bro! 😭😭 Next time, double-check if you’ve already joined, bro bro ☠️")
            return
            
        # 🚨 DITO ANG LOCK! I-set agad sa "ended" para di na mag-trigger sa pangalawang chat
        game_state["phase"] = "ended"
        cancel_timer() 
        
        winner = next(p for p in game_state["players"] if p['id'] == m.from_user.id)
        
        bot.send_message(GROUP_ID, f"🧠 <b>GENIUS ALERT!</b> @{winner['username']} answered {m.text} first and wins!", parse_mode="HTML")
        
        # Reward Logic with Auto-Monitor
        try:
            # Check stock muna bago i-distribute
            inv_db = load_data(DB_FILES["inventory"])
            cat = game_state["prize_cat"]
            
            # Dito natin chine-check kung may stock pa
            if not inv_db.get(cat) or len(inv_db[cat]) < game_state["prize_count"]:
                raise Exception("Out of stock! Admin needs to restock inventory!! Mark mwehehehe:Bruh Tnnr:Hell nah")
            
            distribute_prize([winner])
            # Message for winner in PM
            try:
                bot.send_message(winner['id'], "✅ <b>Prize Redeemed!</b> Automatic credit to your /myowninventory, bro! 🏎️", parse_mode="HTML")
            except:
                pass # Okay lang kung di maka-PM, nasa inventory na niya
                
        except Exception as e:
            # Ito ang lalabas sa group chat kung may problema sa stock
            bot.send_message(GROUP_ID, f"⚠️ <b>Distribution Issue:</b> {str(e)}\n\n<i>Don't worry, the prize is being secured. Please contact the admin!</i>", parse_mode="HTML")
            
        game_state["active"] = False

def math_timeout():
    global game_state
    if game_state.get("phase") == "math_waiting":
        bot.send_message(GROUP_ID, "⏰ <b>Time's up!</b> No one got the correct answer☠️, bro! Next question incoming...!!", parse_mode="HTML")
        # Auto-restart
        start_math_prodigy()

# ==========================================
# 🎮 GAME 8: TREASURE HUNT (12 Boxes, Locked, Super Bomb)
# ==========================================
def start_treasure_hunt():
    global game_state
    if len(game_state["players"]) == 0:
        game_state["active"] = False; return
    
    curr_player = game_state["players"][0]
    
    # I-setup lang ang prizes kung round 1 o bagong laro para hindi mag-reset kada turn
    if "th_prizes" not in game_state.get("extra_data", {}) or game_state["round"] == 1:
        # 12 Boxes: 1 Prize, 6 Bomb, 4 Empty, 1 Super Bomb
        prizes = ["win"] + (["bomb"] * 6) + (["empty"] * 4) + ["super_bomb"]
        random.shuffle(prizes)
        game_state["extra_data"] = {
            "th_prizes": prizes,
            "opened_boxes": [],
            "resolved": False
        }
        
    # Reset lock kada bagong turn
    game_state["extra_data"]["resolved"] = False
    game_state["turn"] = curr_player['id']
    
    opened_boxes = game_state["extra_data"]["opened_boxes"]
    
    # Dynamic buttons: 4 columns para pantay
    markup = InlineKeyboardMarkup(row_width=4)
    buttons = []
    for i in range(12):
        if i in opened_boxes:
            buttons.append(InlineKeyboardButton("🔒", callback_data="th_locked"))
        else:
            buttons.append(InlineKeyboardButton(f"📦 Box {i+1}", callback_data=f"th_{i}"))
            
    markup.add(*buttons)
    
    text = (
        f"🗺️ <b>TREASURE HUNT - Round {game_state['round']}</b>\n\n"
        f"🕵️‍♂️ Explorer: @{curr_player['username']}\n\n"
        f"12 Boxes: 1x 🏆, 6x 💣, 4x 💨, 1x ☢️(Super Bomb)\n\n"
        f"Pick a box bro!"
    )
    
    # Burahin yung lumang message para laging bago sa ilalim
    try:
        if game_state.get("msg_id"):
            bot.delete_message(GROUP_ID, game_state["msg_id"])
    except: pass
    
    msg = bot.send_message(GROUP_ID, text, reply_markup=markup, parse_mode="HTML")
    game_state["msg_id"] = msg.message_id

@bot.callback_query_handler(func=lambda call: call.data.startswith("th_"))
def th_handler(call):
    global game_state
    
    if not game_state["active"] or "th_prizes" not in game_state.get("extra_data", {}):
        return
        
    if call.data == "th_locked":
        bot.answer_callback_query(call.id, "That’s already locked, bro! Pick another one.", show_alert=False)
        return
        
    if call.from_user.id != game_state["turn"]:
        bot.answer_callback_query(call.id, "DON'T CHEAT MY BRO BRO 💀👀", show_alert=True); return
        
    if game_state["extra_data"].get("resolved", False):
        bot.answer_callback_query(call.id, "Processing your choice, chill bro...", show_alert=False)
        return
        
    game_state["extra_data"]["resolved"] = True
    
    idx = int(call.data.split("_")[1])
    game_state["extra_data"]["opened_boxes"].append(idx)
    prize = game_state["extra_data"]["th_prizes"][idx]
    curr_player = game_state["players"][0]
    
    try: bot.delete_message(GROUP_ID, game_state["msg_id"])
    except: pass
    
    if prize == "win":
        bot.send_message(GROUP_ID, f"🎉 <b>JACKPOT!</b> @{curr_player['username']} found the treasure!", parse_mode="HTML")
        distribute_prize([curr_player])
        game_state["active"] = False
        
    elif prize == "bomb":
        bot.send_message(GROUP_ID, f"💥 <b>KABOOM!</b> @{curr_player['username']} opened the bomb and died!", parse_mode="HTML")
        game_state["players"].pop(0)
        
        if len(game_state["players"]) == 1:
            bot.send_message(GROUP_ID, f"🏆 @{game_state['players'][0]['username']} wins by default!")
            distribute_prize(game_state["players"])
            game_state["active"] = False
        elif len(game_state["players"]) == 0:
            bot.send_message(GROUP_ID, "Everyone died! No winners.")
            game_state["active"] = False
        else:
            game_state["round"] += 1
            # Ginamit natin threading timer imbes na time.sleep para walang hang
            threading.Timer(2.0, start_treasure_hunt).start()
            
    elif prize == "super_bomb":
        # ☢️ SUPER BOMB LOGIC: Damay ang sumunod!
        msg_text = f"☢️ <b>SUPER BOMB!</b> @{curr_player['username']} triggered a massive explosion!\n"
        game_state["players"].pop(0) # Patay yung pumindot
        
        if len(game_state["players"]) > 0:
            collateral = game_state["players"].pop(0) # Patay yung kasunod
            msg_text += f"💥 @{collateral['username']} got caught in the blast too! You're both dead, bro! 💀"
            
        bot.send_message(GROUP_ID, msg_text, parse_mode="HTML")
        
        if len(game_state["players"]) == 1:
            bot.send_message(GROUP_ID, f"🏆 @{game_state['players'][0]['username']} wins by default!")
            distribute_prize(game_state["players"])
            game_state["active"] = False
        elif len(game_state["players"]) == 0:
            bot.send_message(GROUP_ID, "Everyone died from the Super Bomb! No winners.")
            game_state["active"] = False
        else:
            game_state["round"] += 1
            threading.Timer(2.5, start_treasure_hunt).start()
            
    else: # Empty
        bot.send_message(GROUP_ID, f"💨 <b>EMPTY!</b> @{curr_player['username']} found nothing. Moving to next player!", parse_mode="HTML")
        game_state["players"].append(game_state["players"].pop(0))
        game_state["round"] += 1
        threading.Timer(2.0, start_treasure_hunt).start()

# ==========================================
# 🎮 GAME 9: TRIPLE LUCK (Smooth & Balanced Group Spin)
# ==========================================
def tl_timeout():
    global game_state
    if not game_state["active"]: return
    
    # Siguraduhing may extra_data at hindi pa naproseso ang round na ito
    if "turn_color" not in game_state["extra_data"] or game_state["extra_data"].get("processing", False):
        return
        
    game_state["extra_data"]["processing"] = True
    color = game_state["extra_data"]["turn_color"]
    pid = game_state["turn"]
    
    # Hanapin ang player na nag-timeout
    try:
        player = next(p for p in game_state["groups"][color] if p['id'] == pid)
        # Tanggalin ang player sa kanyang grupo dahil hindi umabot sa timer
        game_state["groups"][color] = [p for p in game_state["groups"][color] if p['id'] != pid]
        
        try: bot.delete_message(GROUP_ID, game_state["msg_id"])
        except: pass
        
        bot.send_message(GROUP_ID, f"⏰ <b>Time's up!</b>\n\n@{player['username']} was removed from Team <b>{color}</b> for failing to spin! 💀", parse_mode="HTML")
    except StopIteration:
        pass

    # I-check ang mga natitirang grupo na may buhay pang miyembro
    alive_groups = {c: p for c, p in game_state["groups"].items() if len(p) > 0}
    
    if len(alive_groups) == 1:
        winner_color = list(alive_groups.keys())[0]
        winners = alive_groups[winner_color]
        
        # Kunin ang lahat ng usernames ng nanalong grupo
        winner_usernames = "\n".join([f"👤 @{p['username']}" for p in winners])
        
        text = f"🏆 <b>TEAM {winner_color.upper()} WINS BY DEFAULT!</b> 🏆\n───────────────────────\n\n🎉 <b>Winning Group Members:</b>\n{winner_usernames}\n\nAccounts are being distributed! 🎁"
        bot.send_message(GROUP_ID, text, parse_mode="HTML")
        
        distribute_prize(winners)
        game_state["active"] = False
    elif len(alive_groups) == 0:
        bot.send_message(GROUP_ID, "❌ No players or groups left! Tournament cancelled.")
        game_state["active"] = False
    else:
        game_state["round"] += 1
        time.sleep(2)
        start_triple_luck()

def start_triple_luck():
    global game_state
    alive_groups = {c: p for c, p in game_state["groups"].items() if len(p) > 0}
    if len(alive_groups) == 0:
        bot.send_message(GROUP_ID, "No active groups left!"); game_state["active"] = False; return
        
    group_colors = list(alive_groups.keys())
    turn_color = group_colors[game_state["round"] % len(group_colors)]
    
    if "group_turn_idx" not in game_state["extra_data"]:
        game_state["extra_data"] = {
            "group_turn_idx": {c: 0 for c in ["Green", "Blue", "Red", "Yellow"]},
            "processing": False
        }
    else:
        game_state["extra_data"]["processing"] = False
        
    idx = game_state["extra_data"]["group_turn_idx"][turn_color] % len(game_state["groups"][turn_color])
    turn_player = game_state["groups"][turn_color][idx]
    
    game_state["extra_data"]["turn_color"] = turn_color
    game_state["turn"] = turn_player['id']
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🎰 SPIN SLOT MACHINE", callback_data=f"spin_{turn_color}"))
    
    text = (
        f"🎰 <b>TRIPLE LUCK - Round {game_state['round']}</b>\n"
        f"───────────────────────\n\n"
        f"👑 Turn of: @{turn_player['username']}\n"
        f"👥 Team Color: <b>{turn_color}</b>\n\n"
        f"⏱️ <b>Timer: 15 Seconds!</b>\n"
        f"Click the button below to test your team's luck! 👇"
    )
    
    if game_state.get("msg_id"):
        try: bot.delete_message(GROUP_ID, game_state["msg_id"])
        except: pass
        
    msg = bot.send_message(GROUP_ID, text, reply_markup=markup, parse_mode="HTML")
    game_state["msg_id"] = msg.message_id
    
    # I-cancel ang lumang timer kung meron man para iwas overlap
    if "timer_thread" in game_state:
        try: game_state["timer_thread"].cancel()
        except: pass
        
    t = threading.Timer(15.0, tl_timeout)
    game_state["timer_thread"] = t
    t.start()

@bot.callback_query_handler(func=lambda call: call.data.startswith("spin_"))
def spin_handler(call):
    global game_state
    if not game_state["active"] or "turn_color" not in game_state["extra_data"]:
        return
        
    if call.from_user.id != game_state["turn"]:
        bot.answer_callback_query(call.id, "DON'T CHEAT MY BRO BRO 💀👀", show_alert=True); return
        
    # Anti-spam guardrail para sa mabilis na pag-click
    if game_state["extra_data"].get("processing", False):
        bot.answer_callback_query(call.id, "Processing your spin, wait bro...", show_alert=False)
        return
        
    game_state["extra_data"]["processing"] = True
    
    # Patayin agad ang timeout timer
    if "timer_thread" in game_state:
        try: game_state["timer_thread"].cancel()
        except: pass
        
    color = call.data.split("_")[1]
    game_state["extra_data"]["group_turn_idx"][color] += 1
    
    # Balanseng listahan ng prutas para hindi masyadong madali ang natural triple hit
    emojis = ["🍒", "🍋", "🔔", "💎", "7️⃣", "🍇"]
    spin1, spin2, spin3 = random.choice(emojis), random.choice(emojis), random.choice(emojis)
    
    # 🎯 BALANCED JACKPOT RATE: 3% boost chance + natural random hits para siguradong may thrill at hindi tapos agad
    if random.random() < 0.03:
        spin1 = spin2 = spin3 = "7️⃣"
        
    try: bot.delete_message(GROUP_ID, game_state["msg_id"])
    except: pass
    
    bot.send_message(GROUP_ID, f"🎰 @{call.from_user.username} spun the reels for Team {color}:\n\n[ {spin1} | {spin2} | {spin3} ]")
    
    if spin1 == spin2 == spin3:
        winners = game_state["groups"][color]
        # Binuong string ng listahan ng mga ka-team ng nanalo
        winner_usernames = "\n".join([f"👤 @{p['username']}" for p in winners])
        
        text = f"🎉 <b>JACKPOT TRIPLE COMBINATION!</b> 🎉\n───────────────────────\n\n🏆 <b>TEAM {color.upper()} WINS THE TOURNAMENT!</b>\n\n🥇 <b>Winning Team Members:</b>\n{winner_usernames}\n\nCheck your DMs for the rewards! 🚀"
        bot.send_message(GROUP_ID, text, parse_mode="HTML")
        
        distribute_prize(winners)
        game_state["active"] = False
    else:
        game_state["round"] += 1
        time.sleep(1.5) # Swabeng delay bago lumipat sa susunod na team
        start_triple_luck()

# ==========================================
# 🎮 UPDATED TIC TAC TOE (ONE STANDING)
# ==========================================

def start_tic_tac_toe():
    global game_state
    
    # Check kung may sapat pang players para magpatuloy
    if len(game_state["players"]) < 2:
        # Kung isa na lang natira, siya ang champion!
        winner = game_state["players"][0]
        bot.send_message(GROUP_ID, f"🏆 <b>TOURNAMENT CHAMPION: @{winner['username']}!</b>\n\nCongrats, prize is coming!", parse_mode="HTML")
        distribute_prize([winner])
        game_state["active"] = False
        return

    # Kung bagong match (wala pang board o kailangan ng reset)
    if "board" not in game_state["extra_data"] or not game_state["extra_data"].get("active_match"):
        p1 = game_state["players"][0]
        p2 = game_state["players"][1]
        game_state["extra_data"] = {
            "board": ["_"] * 9,
            "p1": p1,
            "p2": p2,
            "turn": p1['id'],
            "symbols": {p1['id']: "❌", p2['id']: "⭕"},
            "active_match": True
        }
        
    board = game_state["extra_data"]["board"]
    p1 = game_state["extra_data"]["p1"]
    p2 = game_state["extra_data"]["p2"]
    curr_turn_id = game_state["extra_data"]["turn"]
    curr_player = p1 if curr_turn_id == p1['id'] else p2
    
    # Ihanda ang listahan ng buhay na players
    alive_players = " | ".join([f"@{p['username']}" for p in game_state["players"]])
    
    markup = InlineKeyboardMarkup(row_width=3)
    buttons = []
    for i in range(9):
        text = "⬜" if board[i] == "_" else board[i]
        buttons.append(InlineKeyboardButton(text, callback_data=f"ttt_{i}"))
    markup.add(*buttons)
    
    msg_text = (
        f"🏃‍♂️ <b>ALIVE PLAYERS:</b>\n{alive_players}\n\n"
        f"❌ <b>TIC TAC TOE MATCH</b> ⭕\n\n"
        f"@{p1['username']} (❌) 🆚 @{p2['username']} (⭕)\n\n"
        f"It's @{curr_player['username']}'s turn!"
    )
    
    if game_state["msg_id"]:
        try: bot.delete_message(GROUP_ID, game_state["msg_id"])
        except: pass
        
    msg = bot.send_message(GROUP_ID, msg_text, reply_markup=markup, parse_mode="HTML")
    game_state["msg_id"] = msg.message_id

@bot.callback_query_handler(func=lambda call: call.data.startswith("ttt_"))
def ttt_handler(call):
    global game_state
    if call.from_user.id != game_state["extra_data"]["turn"]:
        bot.answer_callback_query(call.id, "Wait for your turn bro!☠️ 💀", show_alert=True); return
        
    idx = int(call.data.split("_")[1])
    board = game_state["extra_data"]["board"]
    
    if board[idx] != "_":
        bot.answer_callback_query(call.id, "Spot taken!", show_alert=True); return
        
    sym = game_state["extra_data"]["symbols"][call.from_user.id]
    board[idx] = sym
    
    win_combos = [(0,1,2), (3,4,5), (6,7,8), (0,3,6), (1,4,7), (2,5,8), (0,4,8), (2,4,6)]
    won = any(board[a] == board[b] == board[c] == sym for a,b,c in win_combos)
    
    if won:
        # Identify winner/loser
        p1 = game_state["extra_data"]["p1"]
        p2 = game_state["extra_data"]["p2"]
        winner = p1 if call.from_user.id == p1['id'] else p2
        loser = p2 if call.from_user.id == p1['id'] else p1
        
        bot.send_message(GROUP_ID, f"❌ TIC TAC TOE MATCH ENDED!\n@{winner['username']} wins this round! 🏆", parse_mode="HTML")
        
        # Remove loser from the main players list
        if loser in game_state["players"]:
            game_state["players"].remove(loser)
        
        # Reset board state pero wag i-end ang game_state["active"]
        game_state["extra_data"] = {} # Reset para sa susunod na round
        start_tic_tac_toe()
        
    elif "_" not in board:
        bot.send_message(GROUP_ID, "🤝 <b>DRAW!</b> Nobody wins, resetting board...", parse_mode="HTML")
        game_state["extra_data"]["board"] = ["_"] * 9 # Reset board lang
        start_tic_tac_toe()
        
    else:
        # Switch turn
        game_state["extra_data"]["turn"] = game_state["extra_data"]["p2"]['id'] if call.from_user.id == game_state["extra_data"]["p1"]['id'] else game_state["extra_data"]["p1"]['id']
        start_tic_tac_toe()

# ==========================================
# 🤖 BOT LAUNCH
# ==========================================
print("TNNR Bot Engine Started Smoothly bro! ALL BUGS FIXED & NEW GAMES ☠️ ADDED.")
bot.infinity_polling(skip_pending=True)
