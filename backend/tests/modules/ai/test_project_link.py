"""New conversations may link only an authenticated owner's project."""

from app.models.projects import ResearchProject
from tests.modules.ai.test_assistant import authenticate, create, indexed_paper


def test_create_conversation_project_scope_and_project_deletion(
    client, db, test_user, another_user, access_token
):
    paper, _, _ = indexed_paper(db, test_user.id)
    own = ResearchProject(user_id=test_user.id, title="Mine", objectives=[])
    foreign = ResearchProject(user_id=another_user.id, title="Private", objectives=[])
    db.add_all([own, foreign])
    db.commit()
    own_id, foreign_id = own.id, foreign.id
    db.rollback()
    authenticate(client, access_token)
    for project_id in [foreign_id, 2147483647]:
        response = create(client, [paper.id], project_id=project_id)
        assert response.status_code == 404
        assert "Private" not in response.text
    response = create(client, [paper.id], project_id=own_id)
    assert response.status_code == 201, response.text
    assert response.json()["project_id"] == own_id
    chat_id = response.json()["id"]
    assert (
        client.get(f"/api/v1/projects/{own_id}").json()["conversations"][0]["id"]
        == chat_id
    )
    assert client.delete(f"/api/v1/projects/{own_id}").status_code == 204
    result = client.get(f"/api/v1/conversations/{chat_id}")
    assert result.status_code == 200
    assert result.json()["project_id"] is None
