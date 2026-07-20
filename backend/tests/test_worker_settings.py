from app.core.logging import on_job_end, on_job_start
from app.worker.jobs import (
    aggregate_scan,
    enrich_company,
    evaluate_response,
    execute_prompt,
    finalize_scan,
    generate_prompts,
    verify_profile,
)
from app.worker.settings import InteractiveSettings, PipelineSettings


def test_interactive_settings_registers_the_human_gated_jobs():
    assert InteractiveSettings.functions == [enrich_company, verify_profile]
    assert InteractiveSettings.queue_name == "arq:interactive"
    assert InteractiveSettings.job_timeout == 60
    assert InteractiveSettings.max_jobs == 5
    assert InteractiveSettings.on_job_start is on_job_start
    assert InteractiveSettings.on_job_end is on_job_end


def test_pipeline_settings_registers_the_bulk_jobs():
    assert PipelineSettings.functions == [
        generate_prompts,
        execute_prompt,
        evaluate_response,
        aggregate_scan,
        finalize_scan,
    ]
    assert PipelineSettings.queue_name == "arq:pipeline"
    assert PipelineSettings.job_timeout == 120
    assert PipelineSettings.max_jobs == 20
    assert PipelineSettings.on_job_start is on_job_start
    assert PipelineSettings.on_job_end is on_job_end
