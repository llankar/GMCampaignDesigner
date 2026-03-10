from modules.auto_improve.idea_catalog import get_proposals


def test_get_proposals_returns_non_empty_list():
    proposals = get_proposals(limit=3)
    assert proposals
    assert len(proposals) == 3
    assert all(p.title and p.prompt for p in proposals)
