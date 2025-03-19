from flask import Flask, render_template, request, jsonify
from pymongo import MongoClient
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
from web3 import Web3
from solcx import compile_source, install_solc
import uuid,json
import bcrypt
from cdp_langchain.agent_toolkits import CdpToolkit
from cdp_langchain.utils import CdpAgentkitWrapper
from cdp_langchain.tools import CdpTool
from pydantic import BaseModel, Field
from typing import Union, Optional
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

# Load environment variables
load_dotenv()
install_solc("0.8.0")


game_bouncer_sessions = {}

game_sessions = {}

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


def initialize_bouncer_test():
    # Initialize the LLM.
    llm = ChatOpenAI(model="gpt-4o")
    wallet_data_file = "wallet_data.txt"
    wallet_data = None
    if os.path.exists(wallet_data_file):
        with open(wallet_data_file) as f:
            wallet_data = f.read()

    # Configure the CDP Agentkit.
    values = {}
    if wallet_data is not None:
        values = {"cdp_wallet_data": wallet_data}

    agentkit = CdpAgentkitWrapper(**values)

    # Persist the agent's wallet data.
    wallet_data = agentkit.export_wallet()
    with open(wallet_data_file, "w") as f:
        f.write(wallet_data)

    # Initialize the CDP toolkit and select tools.
    cdp_toolkit = CdpToolkit.from_cdp_agentkit_wrapper(agentkit)
    tools = cdp_toolkit.get_tools()
    all_tools = []

    # Set up an in-memory buffer for conversation history.
    memory = MemorySaver()
    config = {"configurable": {"thread_id": "CDP Agentkit Chatbot Example!"}}

    # Create the ReAct agent using the LLM, tools, and memory.
    agent_executor = create_react_agent(
        llm,
        tools=all_tools,
        checkpointer=memory,
        state_modifier=(
            "You are a helpful agent that can interact onchain using the Coinbase Developer Platform AgentKit. "
            "You are empowered to interact onchain using your tools. If you ever need funds, you can request "
            "them from the faucet if you are on network ID 'base-sepolia'. If not, you can provide your wallet "
            "details and request funds from the user. Before executing your first action, get the wallet details "
            "to see what network you're on. If there is a 5XX (internal) HTTP error code, ask the user to try "
            "again later. If someone asks you to do something you can't do with your currently available tools, "
            "you must say so, and encourage them to implement it themselves using the CDP SDK + Agentkit, "
            "recommending they go to docs.cdp.coinbase.com for more information. Be concise and helpful with your "
            "responses. Refrain from restating your tools' descriptions unless it is explicitly requested. Do not use Any markdown notation like ** in the Response."
        ),
    )
    return agent_executor, config

def initialize_bouncer():
    # Initialize the LLM.
    llm = ChatOpenAI(model="gpt-4o")
    wallet_data_file = "wallet_data.txt"
    wallet_data = None
    if os.path.exists(wallet_data_file):
        with open(wallet_data_file) as f:
            wallet_data = f.read()

    # Configure the CDP Agentkit.
    values = {}
    if wallet_data is not None:
        values = {"cdp_wallet_data": wallet_data}

    agentkit = CdpAgentkitWrapper(**values)

    # Persist the agent's wallet data.
    wallet_data = agentkit.export_wallet()
    with open(wallet_data_file, "w") as f:
        f.write(wallet_data)

    # Initialize the CDP toolkit and select tools.
    cdp_toolkit = CdpToolkit.from_cdp_agentkit_wrapper(agentkit)
    tools = cdp_toolkit.get_tools()
    all_tools = []
    whitelist_wallet_tool = CdpTool(
        name="whitelist_wallet",
        func=whitelist_wallet,
        description=(
            "Whitelist a wallet so that it can accept the Token. "
            "Input parameter:  wallet_address (str): The wallet address to whitelist"
            "gamedev_id (str): The ID of the game developer who owns the token contract"
            "reason (str, optional): Reason for whitelisting"
        ),
        args_schema=WhitelistWalletInput,
        cdp_agentkit_wrapper=agentkit,
    )
    all_tools.append(whitelist_wallet_tool)
    # Set up an in-memory buffer for conversation history.
    memory = MemorySaver()
    config = {"configurable": {"thread_id": "CDP Agentkit Chatbot Example!"}}

    # Create the ReAct agent using the LLM, tools, and memory.
    agent_executor = create_react_agent(
        llm,
        tools=all_tools,
        checkpointer=memory,
        state_modifier=(
            "You are a helpful agent that can interact onchain using the Coinbase Developer Platform AgentKit. "
            "You are empowered to interact onchain using your tools. If you ever need funds, you can request "
            "them from the faucet if you are on network ID 'base-sepolia'. If not, you can provide your wallet "
            "details and request funds from the user. Before executing your first action, get the wallet details "
            "to see what network you're on. If there is a 5XX (internal) HTTP error code, ask the user to try "
            "again later. If someone asks you to do something you can't do with your currently available tools, "
            "you must say so, and encourage them to implement it themselves using the CDP SDK + Agentkit, "
            "recommending they go to docs.cdp.coinbase.com for more information. Be concise and helpful with your "
            "responses. Refrain from restating your tools' descriptions unless it is explicitly requested. Do not use Any markdown notation like ** in the Response."
        ),
    )
    return agent_executor, config



@app.route("/start_bouncer_test", methods=["POST"])
def start_bouncer_test():
    """
    Starts a new game test session.
    Expects JSON input with a "prompt" key containing the initial prompt.
    Returns a unique session_id along with the agent's first response.
    """
    data = request.json
    gamedev_id = data.get("uuid", "")
    gamedev=gamedevs.find_one({'_id': gamedev_id})
    token_list=tokens.find({"creator_uuid":gamedev_id})
    print(token_list)
    rules=f"""Game Description: {gamedev.get("bouncer_rules").get("game_description")}\n\n 
    customer profile: {gamedev.get("bouncer_rules").get("customer_profile")}\n\n 
    token economy: {gamedev.get("bouncer_rules").get("token_economy")}\n\n """
    prompt_suffix = f"""\n You are a bouncer bot that Allows or blocks a user entry into the Arcade.
    You need to quiz the participant based on the rules stated by the developer.
    Mainly focus on the Customer profile rules.. Make this a 4-5 questions exchange one after the other questions. don't ask all the questions at once
    \n\n
    The Game Developer uuid is {gamedev_id}.
    The Wallet Address is 0x4FCFCebac99B81C68Ad4929Aa106ee2E0A94b989. 
    \n\n
    Rules: {rules} """
    # Initialize a new agent instance.
    agent_executor, config = initialize_bouncer_test()

    # Prime the conversation with the initial prompt.
    initial_response = ""
    for chunk in agent_executor.stream(
        {"messages": [HumanMessage(content=prompt_suffix)]}, config
    ):
        if "agent" in chunk:
            # Capture the agent's response (the last such chunk will be used).
            initial_response = chunk["agent"]["messages"][0].content

    # Generate a unique session ID and store the agent instance and config.
    session_id = str(uuid.uuid4())
    game_bouncer_sessions[session_id] = (agent_executor, config)

    return (
        jsonify(
            {
                "session_id": session_id,
                "message": "Game test session started.",
                "initial_response": initial_response,
            }
        ),
        201,
    )


@app.route("/start_bouncer", methods=["POST"])
def start_bouncer():
    """
    Starts a new game test session.
    Expects JSON input with a "prompt" key containing the initial prompt.
    Returns a unique session_id along with the agent's first response.
    """
    data = request.json
    gamedev_id = data.get("uuid", "")
    gamedev=gamedevs.find_one({'_id': gamedev_id})
    rules=f"""Game Description: {gamedev.get("bouncer_rules").get("game_description")}\n\n 
    customer profile: {gamedev.get("bouncer_rules").get("customer_profile")}\n\n 
    token economy: {gamedev.get("bouncer_rules").get("token_economy")}\n\n """
    prompt_suffix = f"""\n You are a bouncer bot that Allows or blocks a user entry into the Arcade.
    You need to quiz the participant based on the rules stated by the developer. 
    Mainly focus on the Customer profile rules. Make this a 4-5 questions exchange one after the other questions. don't ask all the questions at once
    \n\n
    The Game Developer uuid is {gamedev_id}.
    The Wallet Address is 0x4FCFCebac99B81C68Ad4929Aa106ee2E0A94b989. 
    \n\nRules: {rules} """
    # Initialize a new agent instance.
    agent_executor, config = initialize_bouncer()

    # Prime the conversation with the initial prompt.
    initial_response = ""
    for chunk in agent_executor.stream(
        {"messages": [HumanMessage(content=prompt_suffix)]}, config
    ):
        if "agent" in chunk:
            # Capture the agent's response (the last such chunk will be used).
            initial_response = chunk["agent"]["messages"][0].content

    # Generate a unique session ID and store the agent instance and config.
    session_id = str(uuid.uuid4())
    game_bouncer_sessions[session_id] = (agent_executor, config)

    return (
        jsonify(
            {
                "session_id": session_id,
                "message": "Game test session started.",
                "initial_response": initial_response,
            }
        ),
        201,
    )


def initialize_agent():
    """
    Initialize the agent with CDP Agentkit.
    Returns:
        agent_executor: The ReAct agent instance.
        config: A configuration dictionary.
    """
    # Initialize the LLM.
    llm = ChatOpenAI(model="gpt-4o")
    wallet_data_file = "wallet_data.txt"
    wallet_data = None
    if os.path.exists(wallet_data_file):
        with open(wallet_data_file) as f:
            wallet_data = f.read()

    # Configure the CDP Agentkit.
    values = {}
    if wallet_data is not None:
        values = {"cdp_wallet_data": wallet_data}

    agentkit = CdpAgentkitWrapper(**values)

    # Persist the agent's wallet data.
    wallet_data = agentkit.export_wallet()
    with open(wallet_data_file, "w") as f:
        f.write(wallet_data)

    # Initialize the CDP toolkit and select tools.
    cdp_toolkit = CdpToolkit.from_cdp_agentkit_wrapper(agentkit)
    tools = cdp_toolkit.get_tools()
    all_tools = []

    pay_game_fee_tool_instance = CdpTool(
        name="pay_game_fee",
        func=pay_game_fee_tool,
        description=(
            "Pay a game fee by transferring ETH from a user's account to a specified wallet. "
            "Input parameters: user_uuid (str), amount (float, in ether), recipient_wallet (str), game_id (str)."
        ),
        args_schema=PayGameFeeInput,
        cdp_agentkit_wrapper=agentkit,
    )
    transfer_token_tool_instance = CdpTool(
        name="transfer_token",
        func=transfer_token_tool,
        description=(
            "Transfer tokens from a gamedev's wallet to another address. "
            "Input parameters: token_address (str), user_uuid (str), amount (float), gamedev_uuid (str)."
        ),
        args_schema=TransferTokenInput,
        cdp_agentkit_wrapper=agentkit,
    )

    all_tools.append(pay_game_fee_tool_instance)
    all_tools.append(transfer_token_tool_instance)
    # Set up an in-memory buffer for conversation history.
    memory = MemorySaver()
    config = {"configurable": {"thread_id": "CDP Agentkit Chatbot Example!"}}

    # Create the ReAct agent using the LLM, tools, and memory.
    agent_executor = create_react_agent(
        llm,
        tools=all_tools,
        checkpointer=memory,
        state_modifier=(
            "You are a helpful agent that can interact onchain using the Coinbase Developer Platform AgentKit. "
            "You are empowered to interact onchain using your tools. If you ever need funds, you can request "
            "them from the faucet if you are on network ID 'base-sepolia'. If not, you can provide your wallet "
            "details and request funds from the user. Before executing your first action, get the wallet details "
            "to see what network you're on. If there is a 5XX (internal) HTTP error code, ask the user to try "
            "again later. If someone asks you to do something you can't do with your currently available tools, "
            "you must say so, and encourage them to implement it themselves using the CDP SDK + Agentkit, "
            "recommending they go to docs.cdp.coinbase.com for more information. Be concise and helpful with your "
            "responses. Refrain from restating your tools' descriptions unless it is explicitly requested. Do not use Any markdown notation like ** in the Response."
        ),
    )
    return agent_executor, config


def initialize_agent_test():
    """
    Initialize the agent with CDP Agentkit using Nillion AI.
    Returns:
        agent_executor: The ReAct agent instance.
        config: A configuration dictionary.
    """
    # Initialize the LLM.
    llm = ChatOpenAI(model="gpt-4o")
    wallet_data_file = "wallet_data.txt"
    wallet_data = None
    if os.path.exists(wallet_data_file):
        with open(wallet_data_file) as f:
            wallet_data = f.read()

    # Configure the CDP Agentkit.
    values = {}
    if wallet_data is not None:
        values = {"cdp_wallet_data": wallet_data}

    agentkit = CdpAgentkitWrapper(**values)

    # Persist the agent's wallet data.
    wallet_data = agentkit.export_wallet()
    with open(wallet_data_file, "w") as f:
        f.write(wallet_data)

    # Initialize the CDP toolkit and select tools.
    cdp_toolkit = CdpToolkit.from_cdp_agentkit_wrapper(agentkit)
    tools = cdp_toolkit.get_tools()
    all_tools = []

    # Set up an in-memory buffer for conversation history.
    memory = MemorySaver()
    config = {"configurable": {"thread_id": "CDP Agentkit Chatbot Example!"}}

    # Create the ReAct agent using the LLM, tools, and memory.
    agent_executor = create_react_agent(
        llm,
        tools=all_tools,
        checkpointer=memory,
        state_modifier=(
            "You are a helpful agent that can interact onchain using the Coinbase Developer Platform AgentKit. "
            "You are empowered to interact onchain using your tools. If you ever need funds, you can request "
            "them from the faucet if you are on network ID 'base-sepolia'. If not, you can provide your wallet "
            "details and request funds from the user. Before executing your first action, get the wallet details "
            "to see what network you're on. If there is a 5XX (internal) HTTP error code, ask the user to try "
            "again later. If someone asks you to do something you can't do with your currently available tools, "
            "you must say so, and encourage them to implement it themselves using the CDP SDK + Agentkit, "
            "recommending they go to docs.cdp.coinbase.com for more information. Be concise and helpful with your "
            "responses. Refrain from restating your tools' descriptions unless it is explicitly requested. Do not use Any markdown notation like ** in the Response."
        ),
    )
    return agent_executor, config



@app.route("/start_game_test", methods=["POST"])
def start_game_test():
    """
    Starts a new game test session.
    Expects JSON input with a "prompt" key containing the initial prompt.
    Returns a unique session_id along with the agent's first response.
    """
    data = request.json
    game_id = data.get("game_id", "")
    user_uuid = data.get("user_uuid", "NA")
    print(data)
    game = games.find_one({"_id":game_id})
    if game == None:
        return jsonify({"error": "Game not found."}), 404
    prompt = game.get("prompt")
    print(game)
    gamedev = gamedevs.find_one({"_id":game.get("game_developer")})
    if gamedev == None:
        return jsonify({"error": "GameDev not found."}), 404

    prompt_suffix = f"""\n Focus on the Game Prompts and on the Interactions. \n\nThe Winning Condition:\n{game.get("winning_condition")} """
    # Initialize a new agent instance.
    agent_executor, config = initialize_agent_test()

    # Prime the conversation with the initial prompt.
    initial_response = ""
    for chunk in agent_executor.stream(
        {"messages": [HumanMessage(content=prompt + prompt_suffix)]}, config
    ):
        if "agent" in chunk:
            # Capture the agent's response (the last such chunk will be used).
            initial_response = chunk["agent"]["messages"][0].content

    # Generate a unique session ID and store the agent instance and config.
    session_id = str(uuid.uuid4())
    game_sessions[session_id] = (agent_executor, config)

    return (
        jsonify(
            {
                "session_id": session_id,
                "message": "Game test session started.",
                "initial_response": initial_response,
            }
        ),
        201,
    )


@app.route("/start_game", methods=["POST"])
def start_game():
    """
    Starts a new game test session.
    Expects JSON input with a "prompt" key containing the initial prompt.
    Returns a unique session_id along with the agent's first response.
    """
    data = request.json
    game_id = data.get("game_id", "")
    user_uuid = data.get("user_uuid", "NA")

    
    game = games.find_one({"_id":game_id})
    if game == None:
        return jsonify({"error": "Game not found."}), 404
    prompt = game.get("prompt")
    gamedev = gamedevs.find_one({"_id":game.get("game_developer")})
    if gamedev == None:
        return jsonify({"error": "GameDev not found."}), 404
    prompt_suffix = f"""\nThe Winning Condition:\n{game.get("winning_condition")}  \n\n The amount is {game.get("cost_in_eth")} and the recipient_wallet is  {gamedev.get("Wallet Address")}. You need to deduct this on the start of the game everytime. This is absolutely important.
    The Reward for sucess is {game.get("reward_in_tokens")}. You need to add this to the user's wallet in case the user won. You need to use the transfer_token tool for this. 
    The Game Developer uuid is {game["game_developer"]}.
    The user UUID is {user_uuid}. This is important for the payment of the game fee. The Game UUID is {game_id}.
    The Token address for the reward token is {gamedev["Token"]}."""
    # Initialize a new agent instance.
    agent_executor, config = initialize_agent()

    # Prime the conversation with the initial prompt.
    initial_response = ""
    for chunk in agent_executor.stream(
        {"messages": [HumanMessage(content=prompt + prompt_suffix)]}, config
    ):
        if "agent" in chunk:
            # Capture the agent's response (the last such chunk will be used).
            initial_response = chunk["agent"]["messages"][0].content

    # Generate a unique session ID and store the agent instance and config.
    session_id = str(uuid.uuid4())
    game_sessions[session_id] = (agent_executor, config)

    return (
        jsonify(
            {
                "session_id": session_id,
                "message": "Game test session started.",
                "initial_response": initial_response,
            }
        ),
        201,
    )

@app.route("/chat_game/<session_id>", methods=["POST"])
def chat_game(session_id):
    """
    Accepts a user message for the given session and returns the agent's response.
    Expects JSON input with a "message" key.
    """
    data = request.json
    user_input = data.get("message", "")

    if session_id not in game_sessions:
        return jsonify({"error": "Session not found."}), 404

    agent_executor, config = game_sessions[session_id]

    # Send the user's message to the agent and collect the response.
    response_text = ""
    for chunk in agent_executor.stream(
        {"messages": [HumanMessage(content=user_input)]}, config
    ):
        if "agent" in chunk:
            print(chunk["agent"]["messages"][0].content)
            response_text = chunk["agent"]["messages"][0].content
        elif "tools" in chunk:
            print(chunk["tools"]["messages"][0].content)
    return jsonify({"response": response_text})

@app.route("/chat/<session_id>", methods=["POST"])
def chat(session_id):
    """
    Accepts a user message for the given session and returns the agent's response.
    Expects JSON input with a "message" key.
    """
    data = request.json
    user_input = data.get("message", "")

    if session_id not in game_bouncer_sessions:
        return jsonify({"error": "Session not found."}), 404

    agent_executor, config = game_bouncer_sessions[session_id]

    # Send the user's message to the agent and collect the response.
    response_text = ""
    for chunk in agent_executor.stream(
        {"messages": [HumanMessage(content=user_input)]}, config
    ):
        if "agent" in chunk:
            print(chunk["agent"]["messages"][0].content)
            response_text = chunk["agent"]["messages"][0].content
        elif "tools" in chunk:
            print(chunk["tools"]["messages"][0].content)
    return jsonify({"response": response_text})

@app.route("/end_bouncer_test/<session_id>", methods=["POST"])
def end_bouncer_test(session_id):
    """
    Ends the game test session identified by the session_id.
    """
    if session_id in game_bouncer_sessions:
        del game_bouncer_sessions[session_id]
        return jsonify({"message": "Game test session ended."})
    else:
        return jsonify({"error": "Session not found."}), 404
    
    
@app.route("/end_game_test/<session_id>", methods=["POST"])
def end_game_test(session_id):
    """
    Ends the game test session identified by the session_id.
    """
    if session_id in game_sessions:
        del game_sessions[session_id]
        return jsonify({"message": "Game test session ended."})
    else:
        return jsonify({"error": "Session not found."}), 404

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
            'creator': account.address,
            'creator_uuid':gamedev_id,
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

@app.route('/api/create-game', methods=['POST'])
def create_game():
    try:
        # Check if request is multipart form or JSON
        if request.content_type and 'multipart/form-data' in request.content_type:
            # Handle multipart form data
            title = request.form.get('title')
            game_type = request.form.get('game_type')
            cost_in_core = request.form.get('cost_in_core')
            reward_in_tokens = request.form.get('reward_in_tokens')
            token_id = request.form.get('token_id')
            description = request.form.get('description')
            prompt = request.form.get('prompt')
            winning_condition = request.form.get('winning_condition')
            gamedev_id = request.form.get('uuid')
            
            # Handle image upload if present
            image_path = None
            if 'image' in request.files:
                image = request.files['image']
                if image.filename:
                    # Generate unique filename
                    filename = f"{str(uuid.uuid4())}{os.path.splitext(image.filename)[1]}"
                    image_path = f"/static/game_images/{filename}"
                    
                    # Ensure directory exists
                    os.makedirs(os.path.dirname(image_path.lstrip('/')), exist_ok=True)
                    
                    # Save the image
                    image.save(image_path.lstrip('/'))
        else:
            # Handle JSON request
            data = request.json
            title = data.get('title')
            game_type = data.get('game_type')
            cost_in_core = data.get('cost_in_core')
            reward_in_tokens = data.get('reward_in_tokens')
            token_id = data.get('token_id')
            description = data.get('description')
            prompt = data.get('prompt')
            winning_condition = data.get('winning_condition')
            gamedev_id = data.get('uuid')
            image_path = None

        # Validate required fields
        required_fields = {
            'title': title,
            'game_type': game_type,
            'cost_in_core': cost_in_core,
            'reward_in_tokens': reward_in_tokens,
            'token_id': token_id,
            'description': description,
            'prompt': prompt,
            'winning_condition': winning_condition,
            'gamedev_id': gamedev_id
        }
        
        for field_name, field_value in required_fields.items():
            if not field_value:
                return jsonify({'error': f'{field_name} is required'}), 400

        # Check if token exists and belongs to the game developer
        token = tokens.find_one({'_id': token_id})
        if not token:
            return jsonify({'error': 'Token not found'}), 404
            
        if token.get('creator_uuid') != gamedev_id:
            return jsonify({'error': 'You can only use tokens that you created'}), 403

        # Check if gamedev exists
        gamedev = gamedevs.find_one({'_id': gamedev_id})
        if not gamedev:
            return jsonify({'error': 'Game developer not found'}), 404

        # Create game document
        game = {
            '_id': str(uuid.uuid4()),
            'title': title,
            'description': description,
            'prompt': prompt,
            'winning_condition': winning_condition,
            'cost_in_core': float(cost_in_core),
            'reward_in_tokens': int(reward_in_tokens),
            'game_type': int(game_type),
            'token_id': token_id,
            'token_name': token['name'],
            'token_symbol': token['symbol'],
            'token_contract_address': token['contract_address'],
            'revenue': 0.0,
            'players': 0,
            'status': 'inactive',
            'game_developer': gamedev_id,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
        }
        
        if image_path:
            game['image_path'] = image_path

        # Insert into database
        games.insert_one(game)

        return jsonify({
            'message': 'Game created successfully',
            'game_id': game['_id']
        }), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/games', methods=['GET'])
def get_games():
    try:
        # Check if developer_id query parameter is provided
        developer_id = request.args.get('developer_id')
        
        # Build query
        query = {}
        if developer_id:
            query['game_developer'] = developer_id
        
        # Get all games matching the query
        all_games = list(games.find(query))
        
        # Convert ObjectId to string for JSON serialization
        for game in all_games:
            game['_id'] = str(game['_id'])
            if 'token_id' in game:
                game['token_id'] = str(game['token_id'])
            
            # If token information is not already stored in the game document, fetch it
            if 'token_id' in game and not ('token_name' in game and 'token_symbol' in game):
                token = tokens.find_one({'_id': game['token_id']})
                if token:
                    game['token_name'] = token['name']
                    game['token_symbol'] = token['symbol']
                    game['token_contract_address'] = token['contract_address']
        
        return jsonify(all_games), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/games/<game_id>', methods=['GET'])
def get_game(game_id):
    try:
        # Find game by ID
        game = games.find_one({'_id': game_id})
        
        if not game:
            return jsonify({'error': 'Game not found'}), 404
        
        # Convert ObjectId to string for JSON serialization
        game['_id'] = str(game['_id'])
        if 'token_id' in game:
            game['token_id'] = str(game['token_id'])
        
        # If token information is not already stored in the game document, fetch it
        if 'token_id' in game and not ('token_name' in game and 'token_symbol' in game):
            token = tokens.find_one({'_id': game['token_id']})
            if token:
                game['token_name'] = token['name']
                game['token_symbol'] = token['symbol']
                game['token_contract_address'] = token['contract_address']
        
        return jsonify(game), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/games/<game_id>', methods=['DELETE'])
def delete_game(game_id):
    try:
        # Find game by ID
        game = games.find_one({'_id': game_id})
        
        if not game:
            return jsonify({'error': 'Game not found'}), 404
        
        # Delete game image if exists
        if 'image_path' in game and game['image_path']:
            try:
                os.remove(game['image_path'].lstrip('/'))
            except OSError:
                # File doesn't exist or can't be deleted, continue anyway
                pass
        
        # Delete game from database
        games.delete_one({'_id': game_id})
        
        return jsonify({'message': 'Game deleted successfully'}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/games/<game_id>/status', methods=['PATCH'])
def update_game_status(game_id):
    try:
        data = request.json
        status = data.get('status')
        
        if not status:
            return jsonify({'error': 'Status is required'}), 400
        
        if status not in ['active', 'paused', 'inactive']:
            return jsonify({'error': 'Invalid status. Must be one of: active, paused, inactive'}), 400
        
        # Find game by ID
        game = games.find_one({'_id': game_id})
        
        if not game:
            return jsonify({'error': 'Game not found'}), 404
        
        # Update game status
        games.update_one(
            {'_id': game_id},
            {
                '$set': {
                    'status': status,
                    'updated_at': datetime.utcnow()
                }
            }
        )
        
        return jsonify({'message': f'Game status updated to {status}'}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/games/<game_id>/release', methods=['PATCH'])
def release_game(game_id):
    """
    Release a game to production.
    This updates the game status to 'released' and makes it available to players.
    """
    try:
        # Find the game and make sure it exists
        game = games.find_one({"_id": game_id})
        if not game:
            return jsonify({"error": "Game not found"}), 404
            
        # Update the game status to released
        games.update_one(
            {"_id": game_id},
            {"$set": {"status": "released", "release_date": datetime.utcnow()}}
        )
        
        return jsonify({
            "message": "Game successfully released",
            "game_id": game_id,
            "status": "released"
        })
    except Exception as e:
        print(f"Error releasing game: {e}")
        return jsonify({"error": str(e)}), 500

# Add Pydantic model for whitelist wallet input
class WhitelistWalletInput(BaseModel):
    """Input for whitelisting a wallet address."""
    wallet_address: str = Field(
        description="The wallet address to be whitelisted"
    )
    gamedev_id: str = Field(
        description="The ID of the game developer who owns the token contracts"
    )
    reason: Optional[str] = Field(
        default=None,
        description="Optional reason for whitelisting"
    )

# Add whitelist wallet function
def whitelist_wallet(wallet_address: str, gamedev_id: str, reason: Optional[str] = None) -> dict:
    """
    Whitelist a wallet address for all tokens created by the game developer.
    
    Args:
        wallet_address (str): The wallet address to whitelist
        gamedev_id (str): The ID of the game developer who owns the token contracts
        reason (str, optional): Reason for whitelisting
        
    Returns:
        dict: Result of the whitelisting operation
    """
    try:
        # Get game developer from MongoDB
        gamedev = gamedevs.find_one({'_id': gamedev_id})
        if not gamedev:
            return {
                'success': False,
                'error': 'Game developer not found',
                'wallet_address': wallet_address
            }

        # Get all tokens created by the game developer
        developer_tokens = list(tokens.find({'creator_uuid': gamedev_id}))
        if not developer_tokens:
            return {
                'success': False,
                'error': 'No tokens found for this game developer',
                'wallet_address': wallet_address
            }

        # Create account from game developer's private key
        account = web3.eth.account.from_key(gamedev["private_key"])
        
        results = []
        for token in developer_tokens:
            try:
                # Create contract instance for each token
                contract = web3.eth.contract(
                    address=web3.to_checksum_address(token['contract_address']),
                    abi=contract_interface["abi"]
                )
                
                # Build transaction for addToWhitelist
                transaction = contract.functions.addToWhitelist(
                    web3.to_checksum_address(wallet_address)
                ).build_transaction({
                    'from': account.address,
                    'gas': 100000,
                    'gasPrice': web3.eth.gas_price,
                    'nonce': web3.eth.get_transaction_count(account.address),
                    'chainId': web3.eth.chain_id
                })
                
                # Sign and send transaction using game developer's private key
                signed_txn = web3.eth.account.sign_transaction(transaction, account.key.hex())
                tx_hash = web3.eth.send_raw_transaction(signed_txn.raw_transaction)
                receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
                
                results.append({
                    'success': True,
                    'token_name': token['name'],
                    'token_symbol': token['symbol'],
                    'contract_address': token['contract_address'],
                    'transaction_hash': receipt.transactionHash.hex()
                })
            except Exception as e:
                results.append({
                    'success': False,
                    'token_name': token['name'],
                    'token_symbol': token['symbol'],
                    'contract_address': token['contract_address'],
                    'error': str(e)
                })
        
        return {
            'success': True,
            'wallet_address': wallet_address,
            'reason': reason,
            'whitelisting_results': results,
            'total_tokens_processed': len(developer_tokens),
            'successful_whitelists': len([r for r in results if r['success']])
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'wallet_address': wallet_address
        }





########################################
# 2. Pay Game Fee Tool
########################################
def pay_game_fee_tool(
    user_uuid: str, amount: float, recipient_wallet: str, game_id: str
) -> str:
    """
    Pay a game fee by transferring ETH from a user's account to a specified recipient wallet.

    Args:
        user_uuid: The user's UUID.
        amount: The amount of ETH to send (in ether).
        recipient_wallet: The wallet address that will receive the game fee.
        game_id: The Games's UUID.

    Returns:
        A JSON string with a success message and the transaction hash.
    """
    # Retrieve the user's account details using their UUID.
    user = users.find_one({"_id": user_uuid})
    if not user:
        return json.dumps({"error": "User not found"})
    
    try:
        # Create user account from private key
        myacc = web3.eth.account.from_key(user["private_key"])
    except Exception as e:
        return json.dumps({"error": f"Error accessing user wallet: {str(e)}"})
    
    # Convert the fee amount from ether to Wei.
    value = web3.to_wei(amount, "ether")
    gas_price = web3.eth.gas_price

    # Build the transaction: the fee is sent to the provided recipient wallet.
    transaction = {
        "to": recipient_wallet,
        "value": value,
        "gas": 21000,
        "gasPrice": gas_price,
        "nonce": web3.eth.get_transaction_count(myacc.address),
        "chainId": web3.eth.chain_id,
    }

    try:
        # Sign and send the transaction.
        signed_txn = web3.eth.account.sign_transaction(transaction, myacc.key.hex())
        tx_hash = web3.eth.send_raw_transaction(signed_txn.raw_transaction)
        
        # Find the game developer by wallet address
        gamedev = gamedevs.find_one({"wallet_address": recipient_wallet})
        if gamedev:
            # Update gamedev's total revenue
            gamedevs.update_one(
                {"_id": gamedev["_id"]},
                {"$inc": {"total_revenue": amount}}
            )
        
        # Update game stats
        game = games.find_one({"_id": game_id})
        if game:
            games.update_one(
                {"_id": game_id},
                {
                    "$inc": {
                        "revenue": amount,
                        "players": 1
                    }
                }
            )
            
        return json.dumps(
            {"message": "Game fee paid", "transaction_hash": web3.to_hex(tx_hash)}
        )
    except Exception as e:
        return json.dumps({"error": f"Transaction failed: {str(e)}"})

########################################
# 3. Transfer Token Tool
########################################
def transfer_token_tool(
    token_address: str, user_uuid: str, amount: float, gamedev_uuid: str
) -> str:
    """
    Transfer tokens from a gamedev's wallet to another address.

    Args:
        token_address (str): The ERC20 token contract address.
        user_uuid (str): The user id of the destination wallet address.
        amount (float): The amount of tokens to transfer (in human-readable units).
        gamedev_uuid (str): The gamedev user's UUID to look up their private key.

    Returns:
        A JSON string containing a success message and the transaction hash, or an error message.
    """
    try:
        # Retrieve the gamedev's details from the database
        gamedev = gamedevs.find_one({"_id": gamedev_uuid})
        if not gamedev:
            return json.dumps({"error": "Game developer not found"})

        # Get the user's wallet address
        user = users.find_one({"_id": user_uuid})
        if not user:
            return json.dumps({"error": "User not found"})
            
        # Create account instances
        gamedev_account = web3.eth.account.from_key(gamedev["private_key"])
        user_address = user["wallet_address"]

        # Minimal ERC20 ABI for transferring tokens and querying decimals
        ERC20_ABI = [
            {
                "constant": False,
                "inputs": [
                    {"name": "_to", "type": "address"},
                    {"name": "_value", "type": "uint256"},
                ],
                "name": "transfer",
                "outputs": [{"name": "", "type": "bool"}],
                "type": "function",
            },
            {
                "constant": True,
                "inputs": [],
                "name": "decimals",
                "outputs": [{"name": "", "type": "uint8"}],
                "type": "function",
            },
        ]

        # Initialize the token contract
        contract = web3.eth.contract(address=token_address, abi=ERC20_ABI)

        # Retrieve decimals and convert the human-readable amount to the smallest unit
        decimals = contract.functions.decimals().call()
        value = int(amount * (10**decimals))

        # Build the transaction
        transaction = contract.functions.transfer(user_address, value).build_transaction(
            {
                "from": gamedev_account.address,
                "gas": 100000,
                "gasPrice": web3.to_wei("1", "gwei"),
                "nonce": web3.eth.get_transaction_count(gamedev_account.address),
            }
        )

        # Sign and send the transaction
        signed_txn = web3.eth.account.sign_transaction(transaction, gamedev_account.key.hex())
        tx_hash = web3.eth.send_raw_transaction(signed_txn.raw_transaction)

        # Record the transaction
        token_info = tokens.find_one({"contract_address": token_address})
        token_name = token_info["name"] if token_info else "Unknown Token"
        
        # You might want to add a collection for tracking token transfers
        # token_transfers.insert_one({
        #     "token_address": token_address,
        #     "token_name": token_name,
        #     "from": gamedev_account.address,
        #     "to": user_address,
        #     "amount": amount,
        #     "tx_hash": web3.to_hex(tx_hash),
        #     "timestamp": datetime.utcnow()
        # })

        return json.dumps(
            {
                "message": f"Transferred {amount} {token_name} successfully", 
                "transaction_hash": web3.to_hex(tx_hash)
            }
        )
    except Exception as e:
        return json.dumps({"error": str(e)})

class PayGameFeeInput(BaseModel):
    user_uuid: str = Field(..., description="The user's UUID.")
    amount: float = Field(..., description="The amount of ETH to send (in ether).")
    recipient_wallet: str = Field(
        ..., description="The wallet address that will receive the game fee."
    )
    game_id: str = Field(..., description="The Game's UUID.")


class TransferTokenInput(BaseModel):
    token_address: str = Field(..., description="The ERC20 token contract address.")
    user_uuid: str = Field(
        ..., description="The user ID of the destination wallet address."
    )
    amount: float = Field(
        ..., description="The amount of tokens to transfer (in human-readable units)."
    )
    gamedev_uuid: str = Field(
        ..., description="The gamedev user's UUID to look up their private key."
    )

if __name__ == '__main__':
    app.run(debug=True) 