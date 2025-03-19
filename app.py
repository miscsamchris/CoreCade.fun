from flask import Flask, render_template
from pymongo import MongoClient
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
from web3 import Web3
from solcx import compile_source, install_solc

import uuid
# Load environment variables
load_dotenv()
install_solc("0.8.0")

app = Flask(__name__)

# MongoDB Connection
client = MongoClient(os.getenv('MONGODB_URI', 'mongodb://localhost:27017/'))
db = client['corecade_db']

# Collections
tokens = db['tokens']
games = db['games']
gamedevs = db['gamedevs']
users = db['users']

# Web3 Configuration
RPC_URL = "https://rpc.test2.btcs.network"
CHAIN_ID = 1114  # 0x45a
CURRENCY_SYMBOL = "tCORE2"

# Initialize Web3
web3 = Web3(Web3.HTTPProvider(RPC_URL))
private_key = os.getenv("PRIVATE_KEY", "PrivateKey")  # Store securely!
admin = web3.eth.account.from_key(private_key)
web3.eth.default_account = admin.address



ERC20_SOURCE = """
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract ERC20Token {
    string public name;
    string public symbol;
    uint8 public decimals;
    uint256 public totalSupply;
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);

    constructor(string memory _name, string memory _symbol, uint8 _decimals, uint256 _totalSupply) {
        name = _name;
        symbol = _symbol;
        decimals = _decimals;
        totalSupply = _totalSupply * 10 ** uint256(_decimals);
        balanceOf[msg.sender] = totalSupply;
    }

    function transfer(address _to, uint256 _value) public returns (bool success) {
        require(balanceOf[msg.sender] >= _value, "Insufficient balance");
        balanceOf[msg.sender] -= _value;
        balanceOf[_to] += _value;
        emit Transfer(msg.sender, _to, _value);
        return true;
    }

    function approve(address _spender, uint256 _value) public returns (bool success) {
        allowance[msg.sender][_spender] = _value;
        emit Approval(msg.sender, _spender, _value);
        return true;
    }

    function transferFrom(address _from, address _to, uint256 _value) public returns (bool success) {
        require(balanceOf[_from] >= _value, "Insufficient balance");
        require(allowance[_from][msg.sender] >= _value, "Allowance exceeded");
        balanceOf[_from] -= _value;
        balanceOf[_to] += _value;
        allowance[_from][msg.sender] -= _value;
        emit Transfer(_from, _to, _value);
        return true;
    }
}
"""


compiled_sol = compile_source(ERC20_SOURCE, solc_version="0.8.0")
contract_interface = compiled_sol[next(iter(compiled_sol))]
def get_chain_info():
    """Get current chain information"""
    try:
        return {
            'is_connected': web3.is_connected(),
            'chain_id': web3.eth.chain_id,
            'block_number': web3.eth.block_number,
            'gas_price': web3.eth.gas_price,
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
#     users.delete_many({})

#     # Create test tokens
#     test_tokens = [
#         {
#             "_id": str(uuid.uuid4()),
#             "name": "CoreCade Token",
#             "symbol": "CCT",
#             "decimals": 18,
#             "total_supply": "1000000000000000000000000",  # 1 million tokens
#             "balance": "1000000000000000000000000",
#             "contract_address": "0x1234567890123456789012345678901234567890",  # Example address
#             "creator": "0x9876543210987654321098765432109876543210"  # Example address
#         }
#     ]
#     tokens.insert_many(test_tokens)

#     # Create test game developers
#     test_gamedevs = [
#         {
#             "email": "dev@example.com",
#             "company_name": "GameDev Studio",
#             "password": "hashed_password_here",  # In production, use proper password hashing
#             "website": "https://gamedevstudio.com",
#             "description": "Professional game development studio",
#             "wallet_address": "0x1234567890123456789012345678901234567890",
#             "private_key": "private_key_here",  # In production, use secure key management
#             "_id": str(uuid.uuid4()),
#             "verified": True,
#             "total_revenue": 1000.0,
#             "active_status": True,
#             "token": test_tokens[0]["_id"]
#         }
#     ]
#     gamedevs.insert_many(test_gamedevs)

#     # Create test games
#     test_games = [
#         {
#             "_id": str(uuid.uuid4()),
#             "title": "Space Adventure",
#             "description": "An exciting space exploration game",
#             "prompt": "Explore the galaxy and collect resources",
#             "winning_condition": "Collect 1000 resources",
#             "cost_in_core": 0.1,
#             "reward_in_tokens": 100,
#             "game_type": 1,
#             "revenue": 500.0,
#             "players": 100,
#             "status": "active",
#             "imagePath": "/images/space-adventure.jpg",
#             "game_developer": test_gamedevs[0]["_id"]
#         },
#         {
#             "_id": str(uuid.uuid4()),
#             "title": "Puzzle Master",
#             "description": "Brain-teasing puzzle game",
#             "prompt": "Solve complex puzzles to win",
#             "winning_condition": "Complete all levels",
#             "cost_in_eth": 0.05,
#             "reward_in_tokens": 50,
#             "game_type": 2,
#             "revenue": 300.0,
#             "players": 80,
#             "status": "active",
#             "imagePath": "/images/puzzle-master.jpg",
#             "game_developer": test_gamedevs[0]["_id"]
#         }
#     ]
#     games.insert_many(test_games)

#     # Create test users
#     test_users = [
#         {
#             "email": "player@example.com",
#             "basename": "GamePlayer",
#             "password": "hashed_password_here",  # In production, use proper password hashing
#             "wallet_address": "0x9876543210987654321098765432109876543210",
#             "private_key": "private_key_here",  # In production, use secure key management
#             "_id": str(uuid.uuid4())
#         }
#     ]
#     users.insert_many(test_users)

#     return "Test data created successfully!"

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/test-game')
def test_game():
    return render_template('game.html')


if __name__ == '__main__':
    app.run(debug=True) 