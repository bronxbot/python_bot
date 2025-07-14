# BronxBot - Advanced Discord Bot

A comprehensive Discord bot built with nextcord featuring economy, gambling, fishing, trading, and administrative systems.

## Features

### 🏦 Economy System
- Custom currency "bronkbuk" with custom emoji
- Wallet and Bank system with progressive upgrades
- Transaction tracking and leaderboards
- Interest system

### 🎣 Fishing System
- Scalable rarity tiers from common to otherworldly
- Bait and rod system with expandable effects
- Event fish with seasonal availability
- Personality descriptions for each fish
- Personal and global catch statistics

### 🎰 Gambling System
- **Card Games**: Blackjack with splitting & doubling
- **Chance Games**: Slots, Coinflip, Double or Nothing
- **Special Games**: Crash, Roulette, Plinko
- Progressive bet limits and rebalanced odds

### 💼 Work System
- Multiple job types with unique minigames
- Boss relationship system (hostility/loyalty)
- Wage calculation based on performance
- Gift system for boss relationship building

### 🏪 Trading & Bazaar
- Item and currency trading with quick trade feature
- Stock market simulation
- Secret items and analytics tracking

### 🛠️ Administrative Features
- Server settings management
- Message activity tracking
- Command statistics and usage analytics
- Performance monitoring dashboard

## Technical Features

### 🗄️ Database
- MongoDB with async operations
- Connection pooling and automatic retries
- Transaction logging

### 🚀 Performance
- AutoShardedBot for scalability
- Redis caching (optional)
- CPU/Memory monitoring
- Alert system for issues

### 🔧 Development Tools
- Interactive setup wizard
- Service management scripts
- Configuration validation
- Development mode support

## Installation

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Configure environment variables in `.env`
4. Run setup: `python setup.py`
5. Start the bot: `python main.py`

## Configuration

Set up your `.env` file with:
```env
DISCORD_TOKEN=your_discord_token
MONGO_URI=your_mongodb_connection_string
REDIS_URL=your_redis_url (optional)
```

## Project Structure

```
bronx-rewritten/
├── main.py                 # Bot entry point
├── config/                 # Configuration management
├── cogs/                   # Bot command modules
│   ├── economy/           # Economy system
│   ├── fishing/           # Fishing system
│   ├── gambling/          # Gambling games
│   ├── work/              # Work system
│   ├── trading/           # Trading system
│   └── admin/             # Administrative features
├── database/              # Database models and operations
├── utils/                 # Utility functions
├── data/                  # JSON data files
└── scripts/               # Setup and management scripts
```

## License

This project is licensed under the MIT License.
