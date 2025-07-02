# South Bronx Bot
> Gambling on steroids, with an economy in its sidehand, fishing around its waist, and a stock market to tie it all together.

South Bronx bot adds a layer of irony to your server other bots fail to bring to the table, it was literally made because the gambling addiction in /furryporn was so bad we made a bot for it, then other servers wanted it, then we came here.

# __What Makes It Different?__
It's mainly written by one dude, but with all the [contributors on github](https://github.com/bronxbot/bot) (thank you all so much) it's mainly by the people for the people.. But mainly its not for profit, there isn't any premium or cash grab, we do it all for free. For the love of gambling ❤️

# BronxBots Features

## Accepted Variables
All ***economy*** commands that take amount parameters now support these formats:

**Number Formats:**
- `1000` - Regular numbers
- `1k` - 1,000 (K suffix)
- `1.5k` - 1,500 (K suffix with decimals)
- `2m` - 2,000,000 (M suffix) 
- `2.5m` - 2,500,000 (M suffix with decimals)
- `1b` - 1,000,000,000 (B suffix)
- `5.5b` - 5,500,000,000 (B suffix with decimals)

**Scientific Notation:**
- `1e3` - 1,000
- `2.5e5` - 250,000
- `1e6` - 1,000,000

**Percentages:**
- `50%` - 50% of your balance
- `2.5%` - 2.5% of your balance
- `100%` - All your balance

**Special Keywords:**
- `all` / `max` - All available amount
- `half` - Half of your balance

**Supported Commands:**
- `.pay` - Transfer money to users
- `.deposit` - Bank deposits
- `.withdraw` - Bank withdrawals  
- `.crash`, `.blackjack`, `.slots` - All gambling commands
- And more!

# Help
`.h`, `.help`
> sends a modal with buttons that allow you to view every command by category

`.invite`, `.support`
>  get an invite to the BronxBot [support server](https://discord.gg/jvyYWkj3ts)

# AutoFishing
`.auto`
> opens the initial modal for autofishing
> *the autofisher modal also has buttons to quickly use these commands!*

`.auto buy`
> buy an autofisher

`.auto upgrade`
> upgrade the efficiency of your autofishers

`.auto deposit <amount>`
> deposit bronkbuks into your autofishing balance

# Bazaar
> The bazaar is a marketplace / stock market hybrid that gets its price from its visitors
**How it works:**
```python
visitor_factor = len(self.visitors) * 0.5
spending_factor = math.log10(max(1, self.total_spent)) * 10
        
price = self.stock_base_price + visitor_factor + spending_factor
        
# Add some randomness
price *= random.uniform(0.9, 1.1)
```
> - a snippet from the [bazzar.py cog](https://github.com/bronxbot/bot/blob/main/cogs/economy/Bazaar.py) 

`.bazaar`
> View the possible items the bazaar has to offer, buy some stock, or buy some items 
> *There are buttons on this command to quickly do some of the commands below*

`.bazaar-buy <item_id> [amount=1]`
> buy an item from the bazaars shop 

`.bazaar-stock [amount=1]`
> buy bazaar stock

`.secret-bazaar`
> for the prestigious.

`.secret-buy <item_id>`
> for the prestigious to shop.

# Cypher
> I got bored and coded a cyphering thing for e2e conversations through discord bots, its doable?

`.cypher_test [key] [test]`
> runs a decryption and encryption test on a shring

`.cypher [key] [text]`
> **RECOMMENDED** run with no arguments to start a private cypher in DMs

`.decypher [key] [text]`
> **RECOMMENDED** run with no arguments to start a private cypher in DMs

# Economy
> The heart and soul of BronxBot lives here, this isn't quite Kansas yet (gambling), but its what makes the bot go. So let's not take it for granted.

`.balance [member]`
> check your (or a members) wallet, bank & net-worth!

`.bankupgrade`, `.bu`
> purchase a bankupgrade to increase your bank limit

`.beg`
> beg someone for money

`.work`
> work for some easy cash

`.daily`
> get your daily dose of stimulus money

`.pay [member] [amount]`
> pay someone money

`.deposit [amount]`, `.d`, `.dep`
> deposit money into your bank account
> `.deposit all`
> `.deposit 50%`
> `.deposit 3e5`
> `.deposit 1000`

`.withdraw [amount]`, `.w`, `.with`
> withdraw money from your bank account
> `.withdraw all`
> `.withdraw 50%`
> `.withdraw 3e5`
> `.withdraw 1000`

`.leaderboard [scope=server/global]`,`.lb`
> show the leaderboard (or global leaderboard by using `.leaderboard global`)

`.rob [victim]`
> rob somebody

`.trade`
> Trading system commands


# Gambling
> The moment you're all waiting for.

`.blackjack <bet>`,`.bj`
> play a game of blackjack against the bot

`.bomb [channel]`
> start a money bomb in a channel
>
> bombs are time dynamic based on the amount of money spent on a bomb
> 
> anyone who talks in a channel the bomb is currently in has a 50% chance of exploding (the bot will react) and the user will get a random amount of money

`.coinflip <bet> [choice]`
> heads or tails

`.crash <bet> `
> that one game adin ross plays on stream but ported to discord

`.doubleornothing [items]`
> coinflip for items

`.roulette [bet] [choice]`
> play a game of roulette
> 
> **betting guide**
> > number (0-36) - **35:1 payout**
> > red/black - 2:1 payout
> > even/odd - 2:1 payout
> > green(0) - **35:1 payout**
> 
> **usage guide**
> > .rlt 500 red *(bet 500 on red)*
> > .rlt all 7 *(put everything on lucky number 7)*
> > .rlt half odd *(put half your balance on odd)*

`.slots <bet>`
> Play the slots
> 
> Under the hood, a snippet from [line 24-32](https://github.com/bronxbot/bot/blob/main/cogs/economy/Gambling.py)
```python
self.slot_symbols = [
            ("🍒", 30),
            ("🍋", 25),
            ("🍊", 20),
            ("🍇", 15),
            ("🔔", 7),
            ("7️⃣", 3),
            ("💎", 1)
        ]
```
> - these are the weights of the slot machine, feels rigged right? well its not, because we tell you these are the odds.

# Interest
> works by using a base percentage which you can upgrade through a command which eventually requires an item to upgrade

`.interest`, `.i`
> claim your daily interest from your bank

`.interest_upgrade`,`.iu`
> upgrade interest level

`.interest_info`,`.ii`
> get info on your interest rate, among other things..

# Fishing
`.fish`,`.fs`
> go fishing

`.fishinv`, `.finv`
> view the catches 

`.sellfish [fish_id=all]`,`.sf`
> *Fish Ids = Rarities*
> **supported ids:**
> - normal
> - rare
> - event
> - mutated
> - all
> sell your fish based on `id`

`.fishstats`, `.fstats`
> view global fish leaderboards showing the biggest and most expensive fish ever caught with details about who caught them, when, and what gear was used

`.myfishstats [user]`, `.myfs`
> view personal fishing statistics including total catches, value, weight, rarity breakdown, personal records, and recent catches

# Fun
> Literally slop commands, these just do random things and don't belong anywhere

`.ascii <name>`
> Sends ascii art
> *cat, dog, heart, star, shrug, tableflip*

`.8ball [question]`
> ask the almighty 8ball

`.cooldown`
> check command cooldowns

`.guess [max_num=100]`
> starts a higher or lower number guessing game that picks a number in between 1 & max_num

`.hack [user]`
> totally real hacking simulator

`.lovecalc <user1> <user2>`, `.ship`
> very real love calculator aswell

`.pick [item1] [item2] [item3] ...`
> pick a random option from a list
> for people who are indecisive￼, this is your best friend

`.roll [dice=1d6]`
> roll a dice
> format: 2d20 (2 separate 20 dice), 1d6 (one 6 sided dice), etc

`.typingtest [difficulty=easy]`
> do a typing test
> **difficulties:**
> - easy
> - medium
> - hard

`.fireworks`
> enjoy some e-fireworks

`.mathrace [opponent][difficulty=10] `
> Race to solve advanced math problems
Difficulty levels: 1-30

# Text Manipulation
> To staff, please set your filters in your default automod, we are not responsible for the **horrific output due to horrific input**
  
`.mocktext [text]`
> mOcK sOmE tExT lIkE tHiS

`.tinytext [text]`
> convert to ᵗⁱⁿʸ ˢᵘᵖᵉʳˢᶜʳⁱᵖᵗ

`.reverse [text]`
> ʇxǝʇ ruoy esreveɹ

`.owoify [text]`
> uwu-ify youw text owo *nuzzles*

`.emojify [text]`
> turn text into 🔤 regional 🔤 indicators

# Giveaway commands
Add comment
More actions


`.giveaway donate [amount]`
> Donate to server balance


`.giveaway balance`
> Check server balance


`.giveaway list`
> View active giveaways

# Multiplayer
> Fun multiplayer commands you can play with your friends

`.rockpaperscissors3 [opponent] [games=3]`
> Best 2 out of 3 rock-paper-scissors
> Can be extended to any amount of games if need be

`.rollfight [opponent]`
> Challenge someone to a dice duel (highest roll wins)

`.slotbattle [opponent]`
> Challenge someone to a slot battle! Winner takes all, or the house wins if both lose

`.twentyone [opponent]`
> Take turns counting to 21 (who says 21 loses)

`.word_chain [opponent]`
> Play a word chain game! Each word must start with the last letter of the prev...

`.yachtdice [opponent]`
> Play a simplified Yacht dice game


# Shop

`.buy [args]`
> Buy items from the shop

`.daily-deals`
> Show today's special deals

`.globalshop`
> View available items in the global shop

`.inventory`
> View your inventory

`.search <query>`
> Search for items across all shop categories

`.shop_menu [category]`
> View shop items by category

`.shopstats`
> View shop statistics and trends

`.use <item_id>`
> Use an item from your inventory

`.wishlist [action] [item_id]`
> Manage your wishlist


# UtilityAdd commentMore actions

`.afk [reason=AFK]`
> set your AFK status

`.avatar [user]`
> Show a user's avatar

`.banner [user]`
> Show a user's banner.

`.botinfo`
> Show bot statistics and info.

`.calculate <expression>`
> Evaluate a math expression (basic operations only)

`.cleanup [limit=100]`
> Deletes all command messages and bot messages in the channel

`.countdown <future_time>`
> calculate time remaining

`.emojiinfo <emoji>`
> Show info about a custom emoji.

`.emojisteal <emoji>`
> Add an emoji to this server

`.firstmessage [channel]`
> Fetch a channel's first message.

`.hexcolor <hex_code>`
> Show a color preview

`.lottery [max_num=100] [picks=6]`
> generate lottery numbers

`.multipoll <question> [options...]`
> Create a poll with multiple options. Example: .multipoll "Favorite?" "Red" "Blue" "green"

`.ping`
> Show bot latency

`.poll <question>`
> Create a yes or no poll

`.remind [time]`
> Set a reminder. Example: .remind 10m Take a break!

`.roleinfo <role>`
> Show info about a role

`.serverbanner`
> Get the server's banner

`.servericon`
> Get the servers icon

`.serverinfo`
> Get information about the server

`.snipe`
> Show the last deleted message (Within 1 hour of it being deleted)

`.timestamp [style=f]`
> Generate Discord timestamps

`.tinyurl <url>`
> Shorten a URL using TinyURL

`.uptime`
> Show bot uptime

`.userinfo [user]`
> Get information about the user (Accout creation, roles, ID, etc)



# bronx manager

The bronx manager is a terminal interface for managing your bot instance. It provides both a full-featured GUI and a fallback text menu.

## Quick Start

**Important:** Always run the manager from the bronxbot directory.

```bash
cd /path/to/bronx-nextcord
python3 manager.py
```

The manager will automatically detect dependencies and either:
- Launch the terminal GUI (if textual/rich are installed)
- Offer to install dependencies 
- Fall back to a simple text menu

## Manager Features

### Terminal GUI
- **Live status monitoring** - Real-time bot status, server count, latency
- **Live log streaming** - Automatic log updates every 2 seconds
- **Service controls** - Start, stop, restart bot with one click
- **Tray management** - Start/stop system tray (runs in background)
- **Script output** - See real-time output from all management scripts
- **Clean interface** - Minimalist design, easy on the eyes

### Navigation
- `q` - Quit manager
- `r` - Refresh all data
- `s` - Toggle status display
- `l` - Toggle logs display

## Testing & Development

### Test Individual Components

**Test fallback manager:**
```bash
cd /path/to/bronx-nextcord
python3 -c "import sys; sys.path.insert(0, '.'); from manager import run_fallback; run_fallback()"
```

**Test GUI directly:**
```bash
cd /path/to/bronx-nextcord
python3 -c "import sys; sys.path.insert(0, '.'); from manager import run_gui; run_gui()"
```

**Test specific manager functions:**
```bash
cd /path/to/bronx-nextcord
python3 -c "import sys; sys.path.insert(0, '.'); from manager import check_dependencies; print(check_dependencies())"
```

### Manual Script Execution

All management scripts are in the `scripts/` directory:

```bash
# Start bot
bash scripts/start_bot.sh

# Stop bot  
bash scripts/stop_bot.sh

# Check status
bash scripts/status_bot.sh

# View logs
bash scripts/logs_bot.sh

# Start system tray
bash scripts/start_tray.sh

# Setup background service
bash scripts/setup_background.sh
```

### Advanced Usage

**Run manager with specific Python:**
```bash
/home/user/venv/bin/python manager.py
```

**Install dependencies manually:**
```bash
pip install textual rich
```

**Check if manager dependencies are available:**
```bash
python3 -c "
try:
    import textual, rich
    print('✓ GUI dependencies available')
except ImportError as e:
    print(f'✗ Missing: {e}')
"
```

### Troubleshooting

**GUI won't start:**
- Check if textual/rich are installed: `pip list | grep -E "(textual|rich)"`
- Try fallback mode: `python3 -c "from manager import run_fallback; run_fallback()"`

**Tray freezes manager:**
- The manager handles this automatically (runs tray in background)
- Use "stop tray" button to terminate tray application
- Manual stop: `pkill -f bronxbot_tray.py`

**Scripts not found:**
- Ensure you're in the bronxbot directory: `ls bronxbot.py`
- Check scripts directory exists: `ls scripts/`
- Re-run setup if needed: `bash scripts/setup_background.sh`

**Permission issues:**
- Make scripts executable: `chmod +x scripts/*.sh`
- Check directory ownership: `ls -la`

### Manager Development

The manager consists of:
- `manager.py` - Main launcher with dependency checking
- `bronx_manager.py` - async terminal GUI using textual
- `scripts/` - Management scripts (bash)

**Key features:**
- Async operations (non-blocking)
- Live updates (status every 3s, logs every 2s)
- Error handling and recovery
- Cross-platform compatibility
- Fallback support

## Quick Commands Reference

```bash
# Basic usage
python3 manager.py                    # Start manager (auto-detects best mode)

# Testing specific components  
python3 -c "from manager import run_fallback; run_fallback()"     # Test fallback menu
python3 -c "from manager import run_gui; run_gui()"               # Test GUI directly
python3 -c "from manager import check_dependencies; print(check_dependencies())"  # Check deps

# Direct script execution
bash scripts/start_bot.sh             # Start bot manually
bash scripts/stop_bot.sh              # Stop bot manually
bash scripts/status_bot.sh            # Check bot status
pkill -f bronxbot_tray.py             # Stop tray application

# Dependency management
pip install textual rich              # Install GUI dependencies
pip list | grep -E "(textual|rich)"   # Check if GUI deps installed
```

# READ CHANGES.TXT