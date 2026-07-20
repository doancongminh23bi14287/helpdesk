from unittest.mock import patch


def test_mark_user_present_sets_configured_ttl():
    from app.services.presence import mark_user_present

    with patch("app.services.presence.redis_client") as redis_mock, patch(
        "app.services.presence.settings.PRESENCE_ENABLED", True
    ), patch("app.services.presence.settings.PRESENCE_TTL_SECONDS", 90):
        assert mark_user_present(42) is True

    args = redis_mock.setex.call_args.args
    assert args[0] == "presence:user:42"
    assert args[1] == 90
    assert args[2].isdigit()


def test_heartbeat_refreshes_presence_ttl():
    from app.services.presence import mark_user_present

    with patch("app.services.presence.redis_client") as redis_mock, patch(
        "app.services.presence.settings.PRESENCE_ENABLED", True
    ), patch("app.services.presence.settings.PRESENCE_TTL_SECONDS", 90):
        assert mark_user_present(7) is True
        assert mark_user_present(7) is True

    assert redis_mock.setex.call_count == 2
    assert all(call.args[0] == "presence:user:7" for call in redis_mock.setex.call_args_list)


def test_batch_presence_returns_only_non_expired_keys():
    from app.services.presence import get_present_user_ids

    with patch("app.services.presence.redis_client") as redis_mock, patch(
        "app.services.presence.settings.PRESENCE_ENABLED", True
    ):
        redis_mock.mget.return_value = ["timestamp", None, "timestamp"]
        result = get_present_user_ids([1, 2, 3])

    assert result == {1, 3}
    redis_mock.mget.assert_called_once_with(
        ["presence:user:1", "presence:user:2", "presence:user:3"]
    )


def test_redis_failure_degrades_to_neutral_presence():
    from app.services.presence import get_present_user_ids, mark_user_present

    with patch("app.services.presence.redis_client") as redis_mock, patch(
        "app.services.presence.settings.PRESENCE_ENABLED", True
    ):
        redis_mock.setex.side_effect = ConnectionError("redis unavailable")
        redis_mock.mget.side_effect = ConnectionError("redis unavailable")
        assert mark_user_present(1) is False
        assert get_present_user_ids([1, 2]) == set()


def test_disabled_presence_does_not_touch_redis():
    from app.services.presence import get_present_user_ids, mark_user_present

    with patch("app.services.presence.redis_client") as redis_mock, patch(
        "app.services.presence.settings.PRESENCE_ENABLED", False
    ):
        assert mark_user_present(1) is False
        assert get_present_user_ids([1]) == set()

    redis_mock.setex.assert_not_called()
    redis_mock.mget.assert_not_called()
