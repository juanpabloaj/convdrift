from pathlib import Path

from convdrift.parser import load_messages, parse_message
from convdrift.segmenter import segment_messages


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample_transcript.jsonl"


def test_parse_message_extracts_tool_calls_and_tool_results() -> None:
    payload = {
        "isSidechain": False,
        "message": {
            "uuid": "a1",
            "role": "assistant",
            "usage": {
                "input_tokens": 120,
                "output_tokens": 45,
                "cache_read_input_tokens": 300,
                "cache_creation_input_tokens": 10,
            },
            "content": [
                {"type": "text", "text": "Reading files."},
                {
                    "type": "tool_use",
                    "id": "toolu_1",
                    "name": "Read",
                    "input": {"file_path": "README.md"},
                },
            ],
            "createdAt": "2026-04-06T10:00:02Z",
        },
    }

    message = parse_message(payload)

    assert message.role == "assistant"
    assert message.text == "Reading files."
    assert len(message.tool_calls) == 1
    assert message.tool_calls[0].name == "Read"
    assert message.message_kind == "assistant_tool_use"
    assert message.usage is not None
    assert message.usage.input_tokens == 120
    assert message.usage.output_tokens == 45


def test_segment_messages_groups_mainline_and_sidechain_episodes() -> None:
    messages = load_messages(FIXTURE_PATH)

    episodes_by_chain = segment_messages(messages)

    assert set(episodes_by_chain) == {"main", "sidechain:worker-1"}
    assert len(episodes_by_chain["main"]) == 2
    assert len(episodes_by_chain["sidechain:worker-1"]) == 1

    first_main = episodes_by_chain["main"][0]
    assert first_main.message_count == 4
    assert first_main.message_type_counts == {"assistant": 2, "user": 2}

    second_main = episodes_by_chain["main"][1]
    assert second_main.message_count == 2
    assert second_main.message_type_counts == {"assistant": 1, "user": 1}

    sidechain = episodes_by_chain["sidechain:worker-1"][0]
    assert sidechain.message_count == 2
    assert sidechain.user_message.is_sidechain is True


def test_tool_result_only_user_message_does_not_start_new_episode() -> None:
    messages = load_messages(FIXTURE_PATH)

    assert messages[2].message_kind == "tool_result"
    assert messages[2].is_human_input is False

    episodes_by_chain = segment_messages(messages)
    assert episodes_by_chain["main"][0].message_count == 4
