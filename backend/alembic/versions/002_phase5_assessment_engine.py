"""Phase 5 Secure Assessment Engine, Anti-Cheat, and Evaluation Platform Migration

Revision ID: 002_phase5_assessment_engine
Revises: 001_phase3_schema
Create Date: 2026-10-02 14:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '002_phase5_assessment_engine'
down_revision: Union[str, None] = '001_phase3_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. Assessments Table
    op.create_table(
        'assessments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('instructions', sa.Text(), nullable=True),
        sa.Column('duration_minutes', sa.Integer(), nullable=False, server_default='60'),
        sa.Column('start_time', sa.DateTime(), nullable=False),
        sa.Column('end_time', sa.DateTime(), nullable=False),
        sa.Column('max_attempts', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('passing_score', sa.Float(), nullable=False, server_default='50.0'),
        sa.Column('total_marks', sa.Float(), nullable=False, server_default='100.0'),
        sa.Column('negative_marking', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('negative_mark_rate', sa.Float(), nullable=False, server_default='0.25'),
        sa.Column('randomize_questions', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('randomize_options', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('allowed_languages', sa.JSON(), nullable=True),
        sa.Column('candidate_assignment', sa.JSON(), nullable=True),
        sa.Column('anti_cheat_policy', sa.JSON(), nullable=True),
        sa.Column('show_results_immediately', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('allow_review', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='DRAFT'),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_assessments_id'), 'assessments', ['id'], unique=False)
    op.create_index(op.f('ix_assessments_start_time'), 'assessments', ['start_time'], unique=False)
    op.create_index(op.f('ix_assessments_end_time'), 'assessments', ['end_time'], unique=False)
    op.create_index(op.f('ix_assessments_status'), 'assessments', ['status'], unique=False)
    op.create_index(op.f('ix_assessments_created_at'), 'assessments', ['created_at'], unique=False)
    op.create_index('ix_assessments_status_start', 'assessments', ['status', 'start_time'], unique=False)
    op.create_index('ix_assessments_created_by', 'assessments', ['created_by_id'], unique=False)

    # 2. Assessment Questions Table
    op.create_table(
        'assessment_questions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('assessment_id', sa.Integer(), sa.ForeignKey('assessments.id', ondelete='CASCADE'), nullable=False),
        sa.Column('question_id', sa.Integer(), sa.ForeignKey('questions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('section_name', sa.String(length=100), nullable=False, server_default='General'),
        sa.Column('order_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('marks', sa.Float(), nullable=False, server_default='10.0'),
        sa.Column('negative_marks', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('is_mandatory', sa.Boolean(), nullable=False, server_default='1'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('assessment_id', 'question_id', name='uq_assessment_question')
    )
    op.create_index(op.f('ix_assessment_questions_id'), 'assessment_questions', ['id'], unique=False)
    op.create_index(op.f('ix_assessment_questions_assessment_id'), 'assessment_questions', ['assessment_id'], unique=False)
    op.create_index(op.f('ix_assessment_questions_question_id'), 'assessment_questions', ['question_id'], unique=False)
    op.create_index('ix_assessment_questions_assessment_order', 'assessment_questions', ['assessment_id', 'order_index'], unique=False)

    # 3. Assessment Attempts Table
    op.create_table(
        'assessment_attempts',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('assessment_id', sa.Integer(), sa.ForeignKey('assessments.id', ondelete='CASCADE'), nullable=False),
        sa.Column('candidate_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('attempt_number', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='IN_PROGRESS'),
        sa.Column('start_time', sa.DateTime(), nullable=False),
        sa.Column('expiry_time', sa.DateTime(), nullable=False),
        sa.Column('submitted_at', sa.DateTime(), nullable=True),
        sa.Column('seed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('question_order', sa.JSON(), nullable=True),
        sa.Column('option_mapping', sa.JSON(), nullable=True),
        sa.Column('integrity_score', sa.Float(), nullable=False, server_default='100.0'),
        sa.Column('score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('total_marks', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('percentage', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('accuracy', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('passed', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('client_ip', sa.String(length=100), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('session_token', sa.String(length=128), nullable=True),
        sa.Column('last_heartbeat_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_assessment_attempts_id'), 'assessment_attempts', ['id'], unique=False)
    op.create_index(op.f('ix_assessment_attempts_assessment_id'), 'assessment_attempts', ['assessment_id'], unique=False)
    op.create_index(op.f('ix_assessment_attempts_candidate_id'), 'assessment_attempts', ['candidate_id'], unique=False)
    op.create_index(op.f('ix_assessment_attempts_status'), 'assessment_attempts', ['status'], unique=False)
    op.create_index(op.f('ix_assessment_attempts_start_time'), 'assessment_attempts', ['start_time'], unique=False)
    op.create_index(op.f('ix_assessment_attempts_expiry_time'), 'assessment_attempts', ['expiry_time'], unique=False)
    op.create_index(op.f('ix_assessment_attempts_submitted_at'), 'assessment_attempts', ['submitted_at'], unique=False)
    op.create_index(op.f('ix_assessment_attempts_session_token'), 'assessment_attempts', ['session_token'], unique=False)
    op.create_index('ix_assessment_attempts_assessment_user', 'assessment_attempts', ['assessment_id', 'candidate_id'], unique=False)
    op.create_index('ix_assessment_attempts_status_expiry', 'assessment_attempts', ['status', 'expiry_time'], unique=False)

    # 4. Attempt Answers Table
    op.create_table(
        'attempt_answers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('attempt_id', sa.String(length=64), sa.ForeignKey('assessment_attempts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('question_id', sa.Integer(), sa.ForeignKey('questions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('answer_data', sa.JSON(), nullable=True),
        sa.Column('is_flagged', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('is_evaluated', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('score_awarded', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('evaluation_verdict', sa.String(length=50), nullable=True),
        sa.Column('evaluation_details', sa.JSON(), nullable=True),
        sa.Column('execution_time_ms', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('memory_used_kb', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('saved_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('attempt_id', 'question_id', name='uq_attempt_question_answer')
    )
    op.create_index(op.f('ix_attempt_answers_id'), 'attempt_answers', ['id'], unique=False)
    op.create_index(op.f('ix_attempt_answers_attempt_id'), 'attempt_answers', ['attempt_id'], unique=False)
    op.create_index(op.f('ix_attempt_answers_question_id'), 'attempt_answers', ['question_id'], unique=False)
    op.create_index('ix_attempt_answers_attempt_q', 'attempt_answers', ['attempt_id', 'question_id'], unique=False)

    # 5. Anti-Cheat Events Table
    op.create_table(
        'anti_cheat_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('attempt_id', sa.String(length=64), sa.ForeignKey('assessment_attempts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('candidate_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('severity', sa.String(length=50), nullable=False, server_default='INFO'),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_anti_cheat_events_id'), 'anti_cheat_events', ['id'], unique=False)
    op.create_index(op.f('ix_anti_cheat_events_attempt_id'), 'anti_cheat_events', ['attempt_id'], unique=False)
    op.create_index(op.f('ix_anti_cheat_events_candidate_id'), 'anti_cheat_events', ['candidate_id'], unique=False)
    op.create_index(op.f('ix_anti_cheat_events_event_type'), 'anti_cheat_events', ['event_type'], unique=False)
    op.create_index(op.f('ix_anti_cheat_events_severity'), 'anti_cheat_events', ['severity'], unique=False)
    op.create_index(op.f('ix_anti_cheat_events_timestamp'), 'anti_cheat_events', ['timestamp'], unique=False)
    op.create_index('ix_anti_cheat_events_attempt_time', 'anti_cheat_events', ['attempt_id', 'timestamp'], unique=False)
    op.create_index('ix_anti_cheat_events_candidate_time', 'anti_cheat_events', ['candidate_id', 'timestamp'], unique=False)

    # 6. Assessment Results Table
    op.create_table(
        'assessment_results',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('attempt_id', sa.String(length=64), sa.ForeignKey('assessment_attempts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('assessment_id', sa.Integer(), sa.ForeignKey('assessments.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('total_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('max_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('percentage', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('accuracy', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('passed', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('total_questions', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('attempted_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('correct_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('incorrect_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('skipped_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('time_spent_seconds', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('question_breakdown', sa.JSON(), nullable=True),
        sa.Column('section_breakdown', sa.JSON(), nullable=True),
        sa.Column('difficulty_breakdown', sa.JSON(), nullable=True),
        sa.Column('topic_breakdown', sa.JSON(), nullable=True),
        sa.Column('percentile', sa.Float(), nullable=True),
        sa.Column('rank', sa.Integer(), nullable=True),
        sa.Column('total_candidates', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('attempt_id', name='uq_assessment_result_attempt')
    )
    op.create_index(op.f('ix_assessment_results_id'), 'assessment_results', ['id'], unique=False)
    op.create_index(op.f('ix_assessment_results_attempt_id'), 'assessment_results', ['attempt_id'], unique=True)
    op.create_index(op.f('ix_assessment_results_assessment_id'), 'assessment_results', ['assessment_id'], unique=False)
    op.create_index(op.f('ix_assessment_results_user_id'), 'assessment_results', ['user_id'], unique=False)
    op.create_index('ix_assessment_results_assessment_user', 'assessment_results', ['assessment_id', 'user_id'], unique=False)
    op.create_index('ix_assessment_results_score', 'assessment_results', ['total_score'], unique=False)
    op.create_index('ix_assessment_results_rank', 'assessment_results', ['rank'], unique=False)

def downgrade() -> None:
    op.drop_table('assessment_results')
    op.drop_table('anti_cheat_events')
    op.drop_table('attempt_answers')
    op.drop_table('assessment_attempts')
    op.drop_table('assessment_questions')
    op.drop_table('assessments')
