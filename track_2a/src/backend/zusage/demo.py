"""Copy the fictional class into a private workspace for each demo visitor."""

from copy import deepcopy

from sqlmodel import Session, select

from .db import Application, Classroom, Drill, Interview, StudentProfile, User, new_id
from .security import hash_password


def private_demo(session: Session, role: str) -> User:
    source_teacher = session.exec(select(User).where(User.username == "frau.meier")).one()
    source_class = session.exec(select(Classroom).where(Classroom.teacher_id == source_teacher.id)).one()
    suffix = new_id()
    password = hash_password(new_id() + new_id())
    teacher = User(username=f"demo-{suffix}", display_name=source_teacher.display_name,
                   password_hash=password, role="teacher", onboarded=True)
    session.add(teacher)
    classroom = Classroom(name=source_class.name, school=source_class.school, teacher_id=teacher.id)
    session.add(classroom)
    selected = teacher
    students = session.exec(select(User).where(User.class_id == source_class.id)).all()
    for source in students:
        student = User(**source.model_dump(exclude={"id", "username", "class_id", "password_hash", "created_at"}),
                       username=f"demo-{new_id()}", class_id=classroom.id, password_hash=password)
        session.add(student)
        if role == "student" and source.username == "lea":
            selected = student
        profile = session.get(StudentProfile, source.id)
        if profile:
            session.add(StudentProfile(user_id=student.id, data=deepcopy(profile.data)))
        application_ids = {}
        for app in session.exec(select(Application).where(Application.user_id == source.id)).all():
            clone = Application(**deepcopy(app.model_dump(exclude={"id", "user_id"})), user_id=student.id)
            application_ids[app.id] = clone.id
            session.add(clone)
        interview_ids = {}
        for iv in session.exec(select(Interview).where(Interview.user_id == source.id)).all():
            clone = Interview(**deepcopy(iv.model_dump(exclude={"id", "user_id", "application_id"})),
                              user_id=student.id, application_id=application_ids.get(iv.application_id))
            interview_ids[iv.id] = clone.id
            session.add(clone)
        for drill in session.exec(select(Drill).where(Drill.user_id == source.id)).all():
            session.add(Drill(**deepcopy(drill.model_dump(exclude={"id", "user_id", "source_interview_id"})),
                              user_id=student.id, source_interview_id=interview_ids.get(drill.source_interview_id)))
    session.commit()
    selected.ui_lang = "en"
    profile = session.get(StudentProfile, selected.id)
    if profile:
        profile.data = {**profile.data, "interview_language": "en"}
        session.add(profile)
    session.add(selected)
    session.commit()
    session.refresh(selected)
    return selected
