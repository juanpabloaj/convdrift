from __future__ import annotations

from collections import defaultdict

from .models import Episode, Message


def segment_messages(messages: list[Message]) -> dict[str, list[Episode]]:
    episodes_by_chain: dict[str, list[Episode]] = defaultdict(list)
    current_episode_by_chain: dict[str, Episode] = {}

    for message in messages:
        chain_id = _chain_id_for_message(message)
        current_episode = current_episode_by_chain.get(chain_id)

        if message.is_human_input:
            if current_episode is not None:
                episodes_by_chain[chain_id].append(current_episode)
            current_episode = Episode(
                chain_id=chain_id,
                sequence=len(episodes_by_chain[chain_id]) + 1,
                user_message=message,
                messages=[message],
            )
            current_episode_by_chain[chain_id] = current_episode
            continue

        if current_episode is None:
            continue

        current_episode.messages.append(message)

    for chain_id, episode in current_episode_by_chain.items():
        episodes_by_chain[chain_id].append(episode)

    return dict(episodes_by_chain)


def _chain_id_for_message(message: Message) -> str:
    if not message.is_sidechain:
        return "main"
    if message.agent_id:
        return f"sidechain:{message.agent_id}"
    return "sidechain:unknown"
