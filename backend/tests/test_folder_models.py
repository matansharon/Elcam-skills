from models import db, Folder, SkillFolder, Favorite, Skill


def test_deleting_skill_cascades_membership_and_favorites(app, admin_user, make_skill):
    skill_id = make_skill(admin_user, "Cascade Skill")
    with app.app_context():
        folder = Folder(name="F", created_by=admin_user["id"])
        db.session.add(folder)
        db.session.flush()
        db.session.add(SkillFolder(skill_id=skill_id, folder_id=folder.id))
        db.session.add(Favorite(user_id=admin_user["id"], skill_id=skill_id))
        db.session.commit()

        db.session.delete(db.session.get(Skill, skill_id))
        db.session.commit()

        assert SkillFolder.query.count() == 0
        assert Favorite.query.count() == 0
        assert Folder.query.count() == 1  # folder itself survives


def test_deleting_folder_cascades_subfolders_but_keeps_skills(app, admin_user, make_skill):
    skill_id = make_skill(admin_user, "Kept Skill")
    with app.app_context():
        parent = Folder(name="Parent", created_by=admin_user["id"])
        db.session.add(parent)
        db.session.flush()
        child = Folder(name="Child", parent_id=parent.id, created_by=admin_user["id"])
        db.session.add(child)
        db.session.flush()
        db.session.add(SkillFolder(skill_id=skill_id, folder_id=child.id))
        db.session.commit()

        db.session.delete(db.session.get(Folder, parent.id))
        db.session.commit()

        assert Folder.query.count() == 0        # parent + child both gone
        assert SkillFolder.query.count() == 0    # membership gone
        assert db.session.get(Skill, skill_id) is not None  # skill survives


def test_deleting_user_cascades_favorites(app, admin_user, regular_user, make_skill):
    from models import User
    skill_id = make_skill(admin_user, "Shared Skill")
    with app.app_context():
        db.session.add(Favorite(user_id=regular_user["id"], skill_id=skill_id))
        db.session.commit()
        db.session.delete(db.session.get(User, regular_user["id"]))
        db.session.commit()
        assert Favorite.query.count() == 0
        assert db.session.get(Skill, skill_id) is not None
