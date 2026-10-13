import pytest
from fastapi.testclient import TestClient
from app import app, CONV

client = TestClient(app)

@pytest.fixture(autouse=True)
def clear_conversations():
    """Clear the server-side conversation store before each test."""
    CONV.clear()
    yield

def test_chat_endpoint_basic():
    """Verify that the /chat endpoint accepts requests and returns a streaming text response."""
    response = client.post(
        "/chat",
        json={"conversation_id": "test-session-1", "user_message": "Hello"}
    )
    assert response.status_code == 200
    assert response.text is not None

def test_conversation_state_persistence():
    """Verify that server-side state properly records user messages under the given conversation ID."""
    response = client.post(
        "/chat",
        json={"conversation_id": "test-session-2", "user_message": "My name is Taylor."}
    )
    assert response.status_code == 200
    assert "test-session-2" in CONV
    
    stored_messages = CONV["test-session-2"]
    user_msgs = [m for m in stored_messages if m["role"] == "user"]
    assert len(user_msgs) == 1
    assert user_msgs[0]["content"] == "My name is Taylor."

def test_knowledge_base_tool_trigger():
    """Test sending a policy query designed to trigger the knowledge base lookup tool."""
    response = client.post(
        "/chat",
        json={"conversation_id": "test-session-3", "user_message": "What is the cancellation policy?"}
    )
    assert response.status_code == 200

def test_room_availability_tool_trigger():
    """Test sending a reservation query designed to trigger the room availability tool."""
    response = client.post(
        "/chat",
        json={"conversation_id": "test-session-4", "user_message": "Do you have king suites available next weekend?"}
    )
    assert response.status_code == 200

def test_invalid_payload_handling():
    """Verify that submitting malformed or missing fields returns a 422 Unprocessable Entity error."""
    response = client.post(
        "/chat",
        json={"invalid_key": "missing required fields"}
    )
    assert response.status_code == 422