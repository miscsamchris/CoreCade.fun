from flask import Flask, render_template, request, jsonify
from pymongo import MongoClient
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
from web3 import Web3
from solcx import compile_source, install_solc
import uuid
import bcrypt
import jwt

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

# JWT Configuration
JWT_SECRET = os.getenv('JWT_SECRET', 'your-secret-key')  # In production, use a secure secret key
JWT_EXPIRATION = timedelta(days=1)

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
    mapping(address => bool) public isWhitelisted;
    address public owner;

    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);
    event WhitelistAdded(address indexed account);
    event WhitelistRemoved(address indexed account);

    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner can call this function");
        _;
    }

    modifier isAddressWhitelisted(address _address) {
        require(isWhitelisted[_address], "Address is not whitelisted");
        _;
    }

    constructor(string memory _name, string memory _symbol, uint8 _decimals, uint256 _totalSupply) {
        name = _name;
        symbol = _symbol;
        decimals = _decimals;
        totalSupply = _totalSupply * 10 ** uint256(_decimals);
        balanceOf[msg.sender] = totalSupply;
        owner = msg.sender;
        
        // Automatically whitelist the contract creator
        isWhitelisted[msg.sender] = true;
        emit WhitelistAdded(msg.sender);
    }

    function addToWhitelist(address _address) public onlyOwner {
        require(_address != address(0), "Cannot whitelist zero address");
        require(!isWhitelisted[_address], "Address already whitelisted");
        
        isWhitelisted[_address] = true;
        emit WhitelistAdded(_address);
    }

    function removeFromWhitelist(address _address) public onlyOwner {
        require(_address != owner, "Cannot remove owner from whitelist");
        require(isWhitelisted[_address], "Address not whitelisted");
        
        isWhitelisted[_address] = false;
        emit WhitelistRemoved(_address);
    }

    function transfer(address _to, uint256 _value) public isAddressWhitelisted(msg.sender) returns (bool success) {
        require(_to != address(0), "Cannot transfer to zero address");
        require(balanceOf[msg.sender] >= _value, "Insufficient balance");
        require(isWhitelisted[_to], "Recipient is not whitelisted");

        balanceOf[msg.sender] -= _value;
        balanceOf[_to] += _value;
        emit Transfer(msg.sender, _to, _value);
        return true;
    }

    function approve(address _spender, uint256 _value) public isAddressWhitelisted(msg.sender) returns (bool success) {
        require(_spender != address(0), "Cannot approve zero address");
        require(isWhitelisted[_spender], "Spender is not whitelisted");

        allowance[msg.sender][_spender] = _value;
        emit Approval(msg.sender, _spender, _value);
        return true;
    }

    function transferFrom(address _from, address _to, uint256 _value) public isAddressWhitelisted(msg.sender) returns (bool success) {
        require(_from != address(0), "Cannot transfer from zero address");
        require(_to != address(0), "Cannot transfer to zero address");
        require(balanceOf[_from] >= _value, "Insufficient balance");
        require(allowance[_from][msg.sender] >= _value, "Allowance exceeded");
        require(isWhitelisted[_from], "Sender is not whitelisted");
        require(isWhitelisted[_to], "Recipient is not whitelisted");

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

@app.route('/developers')
def developers_home():
    return render_template('gamedev-home.html')

@app.route('/gamedev/signup', methods=['POST'])
def gamedev_signup():
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['email', 'company_name', 'password']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400

        # Check if email already exists
        if gamedevs.find_one({'email': data['email']}):
            return jsonify({'error': 'Email already registered'}), 409

        # Generate a new wallet for the gamedev
        account = web3.eth.account.create()
        value = web3.to_wei(0.01, "ether")
        gas_price = web3.eth.gas_price
        print(f"Gas Price: {gas_price}")
        print(f"Value: {value}")
        # Build transaction
        transaction = {
            "to": account.address,
            "value": value,
            "gas": 21000,
            "gasPrice": web3.eth.gas_price,
            "nonce": web3.eth.get_transaction_count(admin.address),
            "chainId": web3.eth.chain_id,
        }
        # Sign and send transaction
        signed_txn = web3.eth.account.sign_transaction(transaction, admin.key.hex())
        tx_hash = web3.eth.send_raw_transaction(signed_txn.raw_transaction)
        # Hash the password
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(data['password'].encode('utf-8'), salt)

        # Create gamedev document
        gamedev = {
            '_id': str(uuid.uuid4()),
            'email': data['email'],
            'company_name': data['company_name'],
            'password': hashed_password,
            'website': data.get('website', ''),
            'description': data.get('description', ''),
            'wallet_address': account.address,
            'private_key': account.key.hex(),  # In production, encrypt this
            'verified': False,
            'total_revenue': 0.0,
            'active_status': True,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
        }

        # Insert into database
        gamedevs.insert_one(gamedev)

        return jsonify({
            'message': 'Game developer registered successfully',
            'uuid': gamedev['_id'],
            'wallet_adress': str(account.address)
        }), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/gamedev/login', methods=['POST'])
def gamedev_login():
    try:
        data = request.get_json()
        print(data)
        # Validate required fields
        if not data.get('email') or not data.get('password'):
            return jsonify({'error': 'Email and password are required'}), 400

        # Find gamedev by email
        gamedev = gamedevs.find_one({'email': data['email']})
        if not gamedev:
            return jsonify({'error': 'Invalid email or password'}), 401

        # Verify password
        if not bcrypt.checkpw(data['password'].encode('utf-8'), gamedev['password']):
            return jsonify({'error': 'Invalid email or password'}), 401

        return jsonify({
            'message': 'Login successful',
            'user_id': gamedev['_id'],
            'email': gamedev['email'],
            'uuid': gamedev['_id'],
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/gamedev/dashboard')
def gamedev_dashboard():
    return render_template('gamedev-dashboard.html')

@app.route('/api/create-token', methods=['POST'])
def create_token():
    try:
        data = request.get_json()
        print(data)
        # Validate required fields
        required_fields = ['name', 'symbol', 'decimals', 'totalSupply']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400
        gamedev_id=str(data.get("uuid"))
        print(gamedev_id)
        gamedev = gamedevs.find_one({'_id': gamedev_id})
        print(gamedev)
        
        account = web3.eth.account.from_key(gamedev["private_key"])
        ERC20 = web3.eth.contract(
            abi=contract_interface["abi"], bytecode=contract_interface["bin"]
        )

        # Build transaction
        transaction = ERC20.constructor(
            data.get("name"), data.get("symbol"), int(data.get("decimals")),int(data.get("totalSupply"))
        ).build_transaction(
            {
                "from": account.address,
                "gas": 1000000,
                "gasPrice": web3.to_wei("1", "gwei"),
                "nonce": web3.eth.get_transaction_count(account.address),
            }
        )

        # Sign and send
        signed_txn = web3.eth.account.sign_transaction(transaction, account.key.hex())
        tx_hash = web3.eth.send_raw_transaction(signed_txn.raw_transaction)
        tx_receipt = web3.eth.wait_for_transaction_receipt(tx_hash)

        contract_address = tx_receipt.contractAddress

        # Create token document
        token_doc = {
            '_id': str(uuid.uuid4()),
            'name': data['name'],
            'symbol': data['symbol'],
            'decimals': data['decimals'],
            'total_supply': str(int(data['totalSupply']) * (10 ** data['decimals'])),
            'contract_address': contract_address,
            'creator': admin.address,
            'created_at': datetime.utcnow()
        }

        # Save to database
        tokens.insert_one(token_doc)

        return jsonify({
            'message': 'Token created successfully',
            'contract_address': contract_address,
            'token_id': token_doc['_id']
        }), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/tokens', methods=['GET'])
def get_tokens():
    try:
        # Get all tokens from the database
        all_tokens = list(tokens.find())
        
        # Convert ObjectId to string for JSON serialization
        for token in all_tokens:
            token['_id'] = str(token['_id'])
        
        return jsonify(all_tokens), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/tokenguard/settings', methods=['POST'])
def save_tokenguard_settings():
    try:
        data = request.get_json()
        print(data)
        # Validate required fields
        required_fields = ['gameDescription', 'customerProfile', 'tokenEconomy', 'uuid']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400

        gamedev_id = str(data.get("uuid"))
        print(gamedev_id)
        gamedev = gamedevs.find_one({'_id': gamedev_id})
        print(gamedev)
        
        if not gamedev:
            return jsonify({'error': 'Game developer not found'}), 404

        # Create bouncer rules JSON
        bouncer_rules = {
            'game_description': {
                'content': data['gameDescription'],
                'last_updated': datetime.utcnow().isoformat()
            },
            'customer_profile': {
                'content': data['customerProfile'],
                'last_updated': datetime.utcnow().isoformat()
            },
            'token_economy': {
                'content': data['tokenEconomy'],
                'last_updated': datetime.utcnow().isoformat()
            }
        }

        # Update gamedev document with bouncer rules
        gamedevs.update_one(
            {'_id': gamedev_id},
            {
                '$set': {
                    'bouncer_rules': bouncer_rules,
                    'updated_at': datetime.utcnow()
                }
            }
        )

        return jsonify({
            'message': 'TokenGuard settings saved successfully',
            'bouncer_rules': bouncer_rules
        }), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/tokenguard/rules/<gamedev_id>', methods=['GET'])
def get_tokenguard_rules(gamedev_id):
    try:
        # Find gamedev by ID
        gamedev = gamedevs.find_one({'_id': gamedev_id})
        
        if not gamedev:
            return jsonify({'error': 'Game developer not found'}), 404

        # Return bouncer rules if they exist, otherwise return empty structure
        bouncer_rules = gamedev.get('bouncer_rules', {
            'game_description': {
                'content': '',
                'last_updated': None
            },
            'customer_profile': {
                'content': '',
                'last_updated': None
            },
            'token_economy': {
                'content': '',
                'last_updated': None
            }
        })

        return jsonify(bouncer_rules), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True) 