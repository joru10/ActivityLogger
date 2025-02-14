import asyncio
import pytest
import logging
from reports import generate_activity_report

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@pytest.mark.asyncio
async def test_report_generation():
    """Test complete report generation flow"""
    test_activities = [
        {
            "group": "coding",
            "duration_minutes": 30,
            "description": "Working on LLM integration"
        }
    ]
    
    try:
        report = await generate_activity_report(test_activities)
        
        # Validate report structure
        assert isinstance(report, dict), "Report should be a dictionary"
        assert "executive_summary" in report, "Missing executive_summary"
        assert "details" in report, "Missing details"
        assert "markdown_report" in report, "Missing markdown_report"
        
        # Validate executive summary
        exec_summary = report["executive_summary"]
        assert isinstance(exec_summary, dict), "Executive summary should be a dictionary"
        assert "total_time" in exec_summary, "Missing total_time"
        assert "time_by_group" in exec_summary, "Missing time_by_group"
        assert "progress_report" in exec_summary, "Missing progress_report"
        
        # Validate time calculations
        assert exec_summary["total_time"] == 30, "Total time should match input"
        assert "coding" in exec_summary["time_by_group"], "Group 'coding' should be present"
        assert exec_summary["time_by_group"]["coding"] == 30, "Coding time should match input"
        
        logger.info("Report validation successful")
        logger.info(f"Generated report: {report}")
        
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        raise

if __name__ == "__main__":
    pytest.main([__file__, "-v"])