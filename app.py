from flask import Flask, render_template
from pymongo import MongoClient
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
from web3 import Web3

# Load environment variables
load_dotenv()

app = Flask(__name__)

# MongoDB Connection
client = MongoClient(os.getenv('MONGODB_URI', 'mongodb://localhost:27017/'))
db = client['corecade_db']

# Collections
tokens = db['tokens']
games = db['games']
gamedevs = db['gamedevs']
players = db['players']

# Web3 Configuration
RPC_URL = "https://rpc.test2.btcs.network"
CHAIN_ID = 1114  # 0x45a
CURRENCY_SYMBOL = "tCORE2"

# Initialize Web3
w3 = Web3(Web3.HTTPProvider(RPC_URL))



def get_chain_info():
    """Get current chain information"""
    try:
        return {
            'is_connected': w3.is_connected(),
            'chain_id': w3.eth.chain_id,
            'block_number': w3.eth.block_number,
            'gas_price': w3.eth.gas_price,
        }
    except Exception as e:
        return {
            'is_connected': False,
            'error': str(e)
        }

# def create_test_data():
#     # Clear existing test data
#     tokens.delete_many({})
#     games.delete_many({})
#     gamedevs.delete_many({})
#     players.delete_many({})

#     # Create test tokens
#     test_tokens = [
#         {
#             "token": "test_token_1",
#             "user_id": "player_1",
#             "expires_at": datetime.utcnow() + timedelta(days=7),
#             "created_at": datetime.utcnow(),
#             "type": "auth"
#         },
#         {
#             "token": "test_token_2",
#             "user_id": "dev_1",
#             "expires_at": datetime.utcnow() + timedelta(days=7),
#             "created_at": datetime.utcnow(),
#             "type": "auth"
#         }
#     ]
#     tokens.insert_many(test_tokens)

#     # Create test game developers
#     test_gamedevs = [
#         {
#             "dev_id": "dev_1",
#             "username": "GameMaster",
#             "email": "gamemaster@example.com",
#             "created_at": datetime.utcnow(),
#             "games_created": ["game_1", "game_2"],
#             "bio": "Experienced game developer with 5 years of experience"
#         },
#         {
#             "dev_id": "dev_2",
#             "username": "PixelArtist",
#             "email": "pixel@example.com",
#             "created_at": datetime.utcnow(),
#             "games_created": ["game_3"],
#             "bio": "Indie game developer specializing in pixel art games"
#         }
#     ]
#     gamedevs.insert_many(test_gamedevs)

#     # Create test games
#     test_games = [
#         {
#             "game_id": "game_1",
#             "title": "Space Adventure",
#             "description": "An exciting space exploration game",
#             "developer_id": "dev_1",
#             "created_at": datetime.utcnow(),
#             "genre": "Adventure",
#             "status": "active",
#             "rating": 4.5,
#             "total_plays": 1000
#         },
#         {
#             "game_id": "game_2",
#             "title": "Puzzle Master",
#             "description": "Brain-teasing puzzle game",
#             "developer_id": "dev_1",
#             "created_at": datetime.utcnow(),
#             "genre": "Puzzle",
#             "status": "active",
#             "rating": 4.2,
#             "total_plays": 800
#         },
#         {
#             "game_id": "game_3",
#             "title": "Pixel Quest",
#             "description": "Retro-style platformer",
#             "developer_id": "dev_2",
#             "created_at": datetime.utcnow(),
#             "genre": "Platform",
#             "status": "active",
#             "rating": 4.7,
#             "total_plays": 1200
#         }
#     ]
#     games.insert_many(test_games)

#     # Create test players
#     test_players = [
#         {
#             "player_id": "player_1",
#             "username": "GamePro",
#             "email": "gamepro@example.com",
#             "created_at": datetime.utcnow(),
#             "games_played": ["game_1", "game_2"],
#             "total_score": 15000,
#             "achievements": ["first_win", "speed_runner"]
#         },
#         {
#             "player_id": "player_2",
#             "username": "PuzzleSolver",
#             "email": "puzzle@example.com",
#             "created_at": datetime.utcnow(),
#             "games_played": ["game_2", "game_3"],
#             "total_score": 12000,
#             "achievements": ["puzzle_master", "completionist"]
#         }
#     ]
#     players.insert_many(test_players)

#     return "Test data created successfully!"

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/test-game')
def test_game():
    return render_template('game.html')

@app.route('/create-test-data')
def create_test_data_route():
    return create_test_data()

@app.route('/chain-info')
def chain_info():
    return get_chain_info()

if __name__ == '__main__':
    print(get_chain_info())
    app.run(debug=True) 