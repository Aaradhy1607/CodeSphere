"""Phase 3 Production PostgreSQL Schema with Composite Indexes

Revision ID: 001_phase3_schema
Revises: 
Create Date: 2026-10-02 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '001_phase3_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. Admin Allowlist
    op.create_table(
        'admin_allowlist',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('assigned_role', sa.String(length=50), nullable=False, server_default='ADMIN'),
        sa.Column('added_by', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_admin_allowlist_id'), 'admin_allowlist', ['id'], unique=False)
    op.create_index(op.f('ix_admin_allowlist_email'), 'admin_allowlist', ['email'], unique=True)

    # 2. Users
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False, server_default='STUDENT'),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='ACTIVE'),
        sa.Column('hashed_password', sa.String(length=255), nullable=True),
        sa.Column('avatar_url', sa.String(length=500), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='1'),
        sa.Column('failed_login_attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('locked_until', sa.DateTime(), nullable=True),
        sa.Column('last_login_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_role'), 'users', ['role'], unique=False)
    op.create_index(op.f('ix_users_status'), 'users', ['status'], unique=False)
    op.create_index(op.f('ix_users_created_at'), 'users', ['created_at'], unique=False)
    op.create_index('ix_users_role_status', 'users', ['role', 'status'], unique=False)
    op.create_index('ix_users_email_status', 'users', ['email', 'status'], unique=False)

    # 3. Refresh Tokens
    op.create_table(
        'refresh_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token_hash', sa.String(length=255), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('is_revoked', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('replaced_by_hash', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_refresh_tokens_id'), 'refresh_tokens', ['id'], unique=False)
    op.create_index(op.f('ix_refresh_tokens_user_id'), 'refresh_tokens', ['user_id'], unique=False)
    op.create_index(op.f('ix_refresh_tokens_token_hash'), 'refresh_tokens', ['token_hash'], unique=True)
    op.create_index(op.f('ix_refresh_tokens_expires_at'), 'refresh_tokens', ['expires_at'], unique=False)
    op.create_index('ix_refresh_tokens_user_revoked', 'refresh_tokens', ['user_id', 'is_revoked'], unique=False)

    # 4. Password Reset Tokens
    op.create_table(
        'password_reset_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token_hash', sa.String(length=255), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('is_used', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_password_reset_tokens_id'), 'password_reset_tokens', ['id'], unique=False)
    op.create_index(op.f('ix_password_reset_tokens_user_id'), 'password_reset_tokens', ['user_id'], unique=False)
    op.create_index(op.f('ix_password_reset_tokens_token_hash'), 'password_reset_tokens', ['token_hash'], unique=True)
    op.create_index('ix_password_reset_user_used', 'password_reset_tokens', ['user_id', 'is_used'], unique=False)

    # 5. Audit Logs
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('actor_email', sa.String(length=255), nullable=False),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('ip_address', sa.String(length=100), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True, server_default='SUCCESS'),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_logs_id'), 'audit_logs', ['id'], unique=False)
    op.create_index(op.f('ix_audit_logs_user_id'), 'audit_logs', ['user_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_actor_email'), 'audit_logs', ['actor_email'], unique=False)
    op.create_index(op.f('ix_audit_logs_action'), 'audit_logs', ['action'], unique=False)
    op.create_index(op.f('ix_audit_logs_status'), 'audit_logs', ['status'], unique=False)
    op.create_index(op.f('ix_audit_logs_created_at'), 'audit_logs', ['created_at'], unique=False)
    op.create_index('ix_audit_logs_action_created', 'audit_logs', ['action', 'created_at'], unique=False)
    op.create_index('ix_audit_logs_actor_created', 'audit_logs', ['actor_email', 'created_at'], unique=False)

    # 6. Student Profiles
    op.create_table(
        'student_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('enrollment_no', sa.String(length=50), nullable=False),
        sa.Column('branch', sa.String(length=50), nullable=False),
        sa.Column('academic_year', sa.Integer(), nullable=False),
        sa.Column('phone', sa.String(length=20), nullable=True),
        sa.Column('is_approved', sa.Boolean(), nullable=True, server_default='1'),
        sa.Column('total_events_participated', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('total_lifetime_score', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('total_problems_solved', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('average_score', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('consistency_score', sa.Float(), nullable=True, server_default='100.0'),
        sa.Column('placement_readiness_rating', sa.String(length=50), nullable=True, server_default='Developing'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )
    op.create_index(op.f('ix_student_profiles_id'), 'student_profiles', ['id'], unique=False)
    op.create_index(op.f('ix_student_profiles_enrollment_no'), 'student_profiles', ['enrollment_no'], unique=True)
    op.create_index(op.f('ix_student_profiles_branch'), 'student_profiles', ['branch'], unique=False)
    op.create_index(op.f('ix_student_profiles_academic_year'), 'student_profiles', ['academic_year'], unique=False)
    op.create_index('ix_student_profiles_branch_year', 'student_profiles', ['branch', 'academic_year'], unique=False)
    op.create_index('ix_student_profiles_score', 'student_profiles', ['total_lifetime_score'], unique=False)

    # 7. Events
    op.create_table(
        'events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('target_branch', sa.String(length=50), nullable=True, server_default='ALL'),
        sa.Column('target_year', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('start_time', sa.DateTime(), nullable=False),
        sa.Column('end_time', sa.DateTime(), nullable=False),
        sa.Column('duration_minutes', sa.Integer(), nullable=True, server_default='120'),
        sa.Column('status', sa.String(length=50), nullable=True, server_default='UPCOMING'),
        sa.Column('allow_branch_questions', sa.Boolean(), nullable=True, server_default='0'),
        sa.Column('is_leaderboard_visible', sa.Boolean(), nullable=True, server_default='1'),
        sa.Column('are_solutions_released', sa.Boolean(), nullable=True, server_default='0'),
        sa.Column('are_results_released', sa.Boolean(), nullable=True, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_events_id'), 'events', ['id'], unique=False)
    op.create_index(op.f('ix_events_target_branch'), 'events', ['target_branch'], unique=False)
    op.create_index(op.f('ix_events_target_year'), 'events', ['target_year'], unique=False)
    op.create_index(op.f('ix_events_start_time'), 'events', ['start_time'], unique=False)
    op.create_index(op.f('ix_events_end_time'), 'events', ['end_time'], unique=False)
    op.create_index(op.f('ix_events_status'), 'events', ['status'], unique=False)
    op.create_index('ix_events_status_start', 'events', ['status', 'start_time'], unique=False)
    op.create_index('ix_events_branch_year', 'events', ['target_branch', 'target_year'], unique=False)

    # 8. Questions
    op.create_table(
        'questions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('problem_statement', sa.Text(), nullable=False),
        sa.Column('input_format', sa.Text(), nullable=False),
        sa.Column('output_format', sa.Text(), nullable=False),
        sa.Column('constraints', sa.Text(), nullable=False),
        sa.Column('examples', sa.JSON(), nullable=True),
        sa.Column('topic_tags', sa.JSON(), nullable=True),
        sa.Column('difficulty_score', sa.Integer(), nullable=True, server_default='5'),
        sa.Column('expected_time_complexity', sa.String(length=100), nullable=True, server_default='O(N)'),
        sa.Column('expected_space_complexity', sa.String(length=100), nullable=True, server_default='O(1)'),
        sa.Column('time_limit_seconds', sa.Float(), nullable=True, server_default='2.0'),
        sa.Column('memory_limit_mb', sa.Integer(), nullable=True, server_default='256'),
        sa.Column('reference_solutions', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True, server_default='DRAFT'),
        sa.Column('validation_status', sa.String(length=50), nullable=True, server_default='PENDING'),
        sa.Column('validation_notes', sa.Text(), nullable=True),
        sa.Column('is_ai_generated', sa.Boolean(), nullable=True, server_default='0'),
        sa.Column('ai_prompt_blueprint', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_questions_id'), 'questions', ['id'], unique=False)
    op.create_index(op.f('ix_questions_slug'), 'questions', ['slug'], unique=True)
    op.create_index(op.f('ix_questions_difficulty_score'), 'questions', ['difficulty_score'], unique=False)
    op.create_index(op.f('ix_questions_status'), 'questions', ['status'], unique=False)
    op.create_index(op.f('ix_questions_validation_status'), 'questions', ['validation_status'], unique=False)
    op.create_index(op.f('ix_questions_created_at'), 'questions', ['created_at'], unique=False)
    op.create_index('ix_questions_status_diff', 'questions', ['status', 'difficulty_score'], unique=False)
    op.create_index('ix_questions_validation', 'questions', ['validation_status'], unique=False)

    # 9. Test Cases
    op.create_table(
        'test_cases',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('question_id', sa.Integer(), nullable=False),
        sa.Column('input_data', sa.Text(), nullable=False),
        sa.Column('expected_output', sa.Text(), nullable=False),
        sa.Column('is_hidden', sa.Boolean(), nullable=True, server_default='0'),
        sa.Column('explanation', sa.Text(), nullable=True),
        sa.Column('points', sa.Integer(), nullable=True, server_default='10'),
        sa.ForeignKeyConstraint(['question_id'], ['questions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_test_cases_id'), 'test_cases', ['id'], unique=False)
    op.create_index(op.f('ix_test_cases_question_id'), 'test_cases', ['question_id'], unique=False)
    op.create_index(op.f('ix_test_cases_is_hidden'), 'test_cases', ['is_hidden'], unique=False)
    op.create_index('ix_test_cases_qid_hidden', 'test_cases', ['question_id', 'is_hidden'], unique=False)

    # 10. Event Questions
    op.create_table(
        'event_questions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('event_id', sa.Integer(), nullable=False),
        sa.Column('question_id', sa.Integer(), nullable=False),
        sa.Column('branch_override', sa.String(length=50), nullable=True, server_default='ALL'),
        sa.Column('year_override', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('order_index', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('points', sa.Integer(), nullable=True, server_default='100'),
        sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['question_id'], ['questions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('event_id', 'question_id', 'branch_override', 'year_override', name='uq_event_question_branch_year')
    )
    op.create_index(op.f('ix_event_questions_id'), 'event_questions', ['id'], unique=False)
    op.create_index(op.f('ix_event_questions_event_id'), 'event_questions', ['event_id'], unique=False)
    op.create_index(op.f('ix_event_questions_question_id'), 'event_questions', ['question_id'], unique=False)
    op.create_index('ix_event_questions_event_order', 'event_questions', ['event_id', 'order_index'], unique=False)

    # 11. Submissions
    op.create_table(
        'submissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('event_id', sa.Integer(), nullable=False),
        sa.Column('question_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('code', sa.Text(), nullable=False),
        sa.Column('language', sa.String(length=50), nullable=False),
        sa.Column('verdict', sa.String(length=50), nullable=True, server_default='Pending'),
        sa.Column('passed_test_cases', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('total_test_cases', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('score', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('execution_time_ms', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('memory_used_kb', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('test_case_results', sa.JSON(), nullable=True),
        sa.Column('is_final', sa.Boolean(), nullable=True, server_default='0'),
        sa.Column('submitted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['question_id'], ['questions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_submissions_id'), 'submissions', ['id'], unique=False)
    op.create_index(op.f('ix_submissions_event_id'), 'submissions', ['event_id'], unique=False)
    op.create_index(op.f('ix_submissions_question_id'), 'submissions', ['question_id'], unique=False)
    op.create_index(op.f('ix_submissions_user_id'), 'submissions', ['user_id'], unique=False)
    op.create_index(op.f('ix_submissions_verdict'), 'submissions', ['verdict'], unique=False)
    op.create_index(op.f('ix_submissions_submitted_at'), 'submissions', ['submitted_at'], unique=False)
    op.create_index('ix_submissions_event_user', 'submissions', ['event_id', 'user_id'], unique=False)
    op.create_index('ix_submissions_event_question_user', 'submissions', ['event_id', 'question_id', 'user_id'], unique=False)
    op.create_index('ix_submissions_user_submitted', 'submissions', ['user_id', 'submitted_at'], unique=False)

    # 12. Student Reports
    op.create_table(
        'student_reports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('event_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('score', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('rank', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('total_participants', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('overall_performance_summary', sa.Text(), nullable=False),
        sa.Column('strengths', sa.JSON(), nullable=True),
        sa.Column('areas_for_improvement', sa.JSON(), nullable=True),
        sa.Column('topic_performance', sa.JSON(), nullable=True),
        sa.Column('time_efficiency_rating', sa.String(length=100), nullable=True, server_default='Optimal'),
        sa.Column('problem_solving_pattern', sa.Text(), nullable=True),
        sa.Column('difficulty_handling', sa.Text(), nullable=True),
        sa.Column('comparative_analysis', sa.Text(), nullable=True),
        sa.Column('generated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_student_reports_id'), 'student_reports', ['id'], unique=False)
    op.create_index(op.f('ix_student_reports_event_id'), 'student_reports', ['event_id'], unique=False)
    op.create_index(op.f('ix_student_reports_user_id'), 'student_reports', ['user_id'], unique=False)
    op.create_index(op.f('ix_student_reports_score'), 'student_reports', ['score'], unique=False)
    op.create_index(op.f('ix_student_reports_rank'), 'student_reports', ['rank'], unique=False)
    op.create_index('ix_student_reports_event_rank', 'student_reports', ['event_id', 'rank'], unique=False)
    op.create_index('ix_student_reports_user_event', 'student_reports', ['user_id', 'event_id'], unique=False)

def downgrade() -> None:
    op.drop_table('student_reports')
    op.drop_table('submissions')
    op.drop_table('event_questions')
    op.drop_table('test_cases')
    op.drop_table('questions')
    op.drop_table('events')
    op.drop_table('student_profiles')
    op.drop_table('audit_logs')
    op.drop_table('password_reset_tokens')
    op.drop_table('refresh_tokens')
    op.drop_table('users')
    op.drop_table('admin_allowlist')
