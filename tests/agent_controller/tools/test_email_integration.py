"""
Integration tests for email tools.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from typing import Dict, Any

from tools.email import EmailSearchTool, EmailSummarizeTool, EmailDraftTool
from tools.base import ToolResult, ToolStatus


@pytest.mark.asyncio
class TestEmailSearchToolIntegration:
    """Integration tests for EmailSearchTool."""
    
    @pytest.fixture
    def mock_mcp_client(self):
        """Create a mock MCP client."""
        client = AsyncMock()
        client.search_emails = AsyncMock()
        return client
    
    @pytest.fixture
    def email_search_tool(self, mock_mcp_client):
        """Create EmailSearchTool with mock MCP client."""
        return EmailSearchTool(mcp_client=mock_mcp_client)
    
    async def test_successful_email_search(self, email_search_tool, mock_mcp_client):
        """Test successful email search with MCP client."""
        # Setup mock response
        mock_emails = [
            {
                "id": "email_1",
                "subject": "Test Email 1",
                "sender": "test1@example.com",
                "date": "2024-01-01T10:00:00Z",
                "preview": "This is a test email...",
                "has_attachments": False
            },
            {
                "id": "email_2",
                "subject": "Test Email 2",
                "sender": "test2@example.com",
                "date": "2024-01-01T11:00:00Z",
                "preview": "Another test email...",
                "has_attachments": True
            }
        ]
        mock_mcp_client.search_emails.return_value = mock_emails
        
        # Execute search
        result = await email_search_tool.execute({
            "query": "test query",
            "limit": 10
        })
        
        # Verify result
        assert result.is_success()
        assert result.data["total_results"] == 2
        assert len(result.data["results"]) == 2
        assert result.data["query"] == "test query"
        
        # Verify MCP client was called correctly
        mock_mcp_client.search_emails.assert_called_once()
    
    async def test_search_with_filters(self, email_search_tool, mock_mcp_client):
        """Test email search with various filters."""
        mock_mcp_client.search_emails.return_value = []
        
        # Execute search with filters
        result = await email_search_tool.execute({
            "query": "important meeting",
            "limit": 5,
            "date_from": "2024-01-01",
            "date_to": "2024-01-31",
            "sender": "boss@company.com",
            "has_attachments": True
        })
        
        assert result.is_success()
        assert result.data["total_results"] == 0
        assert "filters_applied" in result.metadata
        
        filters = result.metadata["filters_applied"]
        assert filters["limit"] == 5
        assert filters["date_from"] == "2024-01-01"
        assert filters["sender"] == "boss@company.com"
    
    async def test_search_without_mcp_client(self):
        """Test search falls back to mock data when no MCP client."""
        tool = EmailSearchTool()  # No MCP client
        
        result = await tool.execute({
            "query": "test query",
            "limit": 5
        })
        
        assert result.is_success()
        assert result.data["total_results"] > 0  # Should have mock results
        assert all("email_" in r["id"] for r in result.data["results"])
    
    async def test_search_parameter_validation(self, email_search_tool):
        """Test parameter validation in search tool."""
        # Missing required parameter
        with pytest.raises(Exception):
            await email_search_tool.validate_args({})
        
        # Invalid limit
        with pytest.raises(Exception):
            await email_search_tool.validate_args({
                "query": "test",
                "limit": 200  # Exceeds max
            })
        
        # Valid parameters
        validated = await email_search_tool.validate_args({
            "query": "test query",
            "limit": 10
        })
        assert validated["query"] == "test query"
        assert validated["limit"] == 10


@pytest.mark.asyncio
class TestEmailSummarizeToolIntegration:
    """Integration tests for EmailSummarizeTool."""
    
    @pytest.fixture
    def mock_clients(self):
        """Create mock MCP and LLM clients."""
        mcp_client = AsyncMock()
        llm_client = AsyncMock()
        
        mcp_client.get_email = AsyncMock()
        llm_client.generate = AsyncMock()
        
        return mcp_client, llm_client
    
    @pytest.fixture
    def email_summarize_tool(self, mock_clients):
        """Create EmailSummarizeTool with mock clients."""
        mcp_client, llm_client = mock_clients
        return EmailSummarizeTool(mcp_client=mcp_client, llm_client=llm_client)
    
    async def test_single_email_summarization(self, email_summarize_tool, mock_clients):
        """Test summarizing a single email."""
        mcp_client, llm_client = mock_clients
        
        # Setup mock email content
        mock_email = {
            "id": "email_1",
            "subject": "Project Update",
            "sender": "manager@company.com",
            "body": "This is a detailed project update with multiple points..."
        }
        mcp_client.get_email.return_value = mock_email
        
        # Execute summarization
        result = await email_summarize_tool.execute({
            "email_ids": ["email_1"],
            "summary_type": "brief"
        })
        
        assert result.is_success()
        assert result.data["total_summarized"] == 1
        assert len(result.data["summaries"]) == 1
        
        summary = result.data["summaries"][0]
        assert summary["email_id"] == "email_1"
        assert summary["summary_type"] == "brief"
        assert isinstance(summary["summary"], str)
    
    async def test_multiple_email_summarization(self, email_summarize_tool, mock_clients):
        """Test summarizing multiple emails."""
        mcp_client, llm_client = mock_clients
        
        # Setup mock for multiple emails
        def mock_get_email(email_id):
            return {
                "id": email_id,
                "subject": f"Subject for {email_id}",
                "sender": "sender@example.com",
                "body": f"Body content for {email_id}"
            }
        
        mcp_client.get_email.side_effect = mock_get_email
        
        # Execute summarization
        result = await email_summarize_tool.execute({
            "email_ids": ["email_1", "email_2", "email_3"],
            "summary_type": "detailed",
            "max_length": 200
        })
        
        assert result.is_success()
        assert result.data["total_summarized"] == 3
        assert len(result.data["summaries"]) == 3
        
        # Verify all emails were processed
        email_ids = [s["email_id"] for s in result.data["summaries"]]
        assert "email_1" in email_ids
        assert "email_2" in email_ids
        assert "email_3" in email_ids
    
    async def test_different_summary_types(self, email_summarize_tool):
        """Test different summary types."""
        summary_types = ["brief", "detailed", "action_items", "key_points"]
        
        for summary_type in summary_types:
            result = await email_summarize_tool.execute({
                "email_ids": ["test_email"],
                "summary_type": summary_type
            })
            
            assert result.is_success()
            summary = result.data["summaries"][0]
            assert summary["summary_type"] == summary_type
            assert isinstance(summary["summary"], str)
            assert len(summary["summary"]) > 0
    
    async def test_empty_email_list(self, email_summarize_tool):
        """Test handling of empty email list."""
        with pytest.raises(Exception) as exc_info:
            await email_summarize_tool.execute({
                "email_ids": []
            })
        assert "No email IDs provided" in str(exc_info.value)


@pytest.mark.asyncio
class TestEmailDraftToolIntegration:
    """Integration tests for EmailDraftTool."""
    
    @pytest.fixture
    def mock_clients(self):
        """Create mock MCP and LLM clients."""
        mcp_client = AsyncMock()
        llm_client = AsyncMock()
        
        mcp_client.get_email = AsyncMock()
        llm_client.generate = AsyncMock()
        
        return mcp_client, llm_client
    
    @pytest.fixture
    def email_draft_tool(self, mock_clients):
        """Create EmailDraftTool with mock clients."""
        mcp_client, llm_client = mock_clients
        return EmailDraftTool(mcp_client=mcp_client, llm_client=llm_client)
    
    async def test_new_email_draft(self, email_draft_tool):
        """Test creating a new email draft."""
        result = await email_draft_tool.execute({
            "context": "Schedule a meeting for next week to discuss the project timeline",
            "tone": "professional",
            "recipient": "team@company.com",
            "subject": "Project Timeline Meeting"
        })
        
        assert result.is_success()
        assert result.data["is_reply"] is False
        assert result.data["tone"] == "professional"
        
        draft = result.data["draft"]
        assert draft["to"] == "team@company.com"
        assert draft["subject"] == "Project Timeline Meeting"
        assert isinstance(draft["body"], str)
        assert len(draft["body"]) > 0
    
    async def test_reply_email_draft(self, email_draft_tool, mock_clients):
        """Test creating a reply email draft."""
        mcp_client, llm_client = mock_clients
        
        # Setup original email
        original_email = {
            "id": "original_email",
            "subject": "Question about project",
            "sender": "colleague@company.com",
            "body": "I have a question about the project timeline..."
        }
        mcp_client.get_email.return_value = original_email
        
        result = await email_draft_tool.execute({
            "context": "Answer their question about the timeline and provide an update",
            "reply_to_id": "original_email",
            "tone": "friendly"
        })
        
        assert result.is_success()
        assert result.data["is_reply"] is True
        assert result.data["tone"] == "friendly"
        
        draft = result.data["draft"]
        assert draft["to"] == "colleague@company.com"
        assert "Re:" in draft["subject"]
        assert draft["in_reply_to"] == "original_email"
    
    async def test_different_tones(self, email_draft_tool):
        """Test email drafts with different tones."""
        tones = ["professional", "friendly", "formal", "casual", "urgent"]
        
        for tone in tones:
            result = await email_draft_tool.execute({
                "context": "Follow up on the meeting from yesterday",
                "tone": tone
            })
            
            assert result.is_success()
            assert result.data["tone"] == tone
            draft = result.data["draft"]
            assert isinstance(draft["body"], str)
    
    async def test_invalid_tone(self, email_draft_tool):
        """Test handling of invalid tone."""
        with pytest.raises(Exception):
            await email_draft_tool.validate_args({
                "context": "Test context",
                "tone": "invalid_tone"
            })


@pytest.mark.asyncio
class TestEmailToolsIntegration:
    """Integration tests for email tool workflows."""
    
    async def test_search_summarize_workflow(self):
        """Test workflow: search emails then summarize results."""
        # Create tools
        search_tool = EmailSearchTool()
        summarize_tool = EmailSummarizeTool()
        
        # Step 1: Search for emails
        search_result = await search_tool.execute({
            "query": "important project updates",
            "limit": 3
        })
        
        assert search_result.is_success()
        email_ids = [email["id"] for email in search_result.data["results"]]
        
        # Step 2: Summarize found emails
        summarize_result = await summarize_tool.execute({
            "email_ids": email_ids,
            "summary_type": "key_points"
        })
        
        assert summarize_result.is_success()
        assert len(summarize_result.data["summaries"]) == len(email_ids)
    
    async def test_search_draft_workflow(self):
        """Test workflow: search for context then draft response."""
        # Create tools
        search_tool = EmailSearchTool()
        draft_tool = EmailDraftTool()
        
        # Step 1: Search for relevant emails for context
        search_result = await search_tool.execute({
            "query": "client meeting schedule",
            "limit": 1
        })
        
        assert search_result.is_success()
        
        # Step 2: Draft email based on search context
        if search_result.data["results"]:
            context_email = search_result.data["results"][0]
            draft_result = await draft_tool.execute({
                "context": f"Follow up on {context_email['subject']} discussion",
                "tone": "professional"
            })
            
            assert draft_result.is_success()
            assert "follow up" in draft_result.data["draft"]["body"].lower()
    
    async def test_concurrent_email_operations(self):
        """Test concurrent execution of multiple email tools."""
        search_tool = EmailSearchTool()
        summarize_tool = EmailSummarizeTool()
        draft_tool = EmailDraftTool()
        
        # Execute multiple operations concurrently
        tasks = [
            search_tool.execute({"query": "project A", "limit": 2}),
            search_tool.execute({"query": "project B", "limit": 2}),
            summarize_tool.execute({
                "email_ids": ["mock_email_1"],
                "summary_type": "brief"
            }),
            draft_tool.execute({
                "context": "Schedule team meeting",
                "tone": "professional"
            })
        ]
        
        results = await asyncio.gather(*tasks)
        
        # All operations should succeed
        assert all(result.is_success() for result in results)
        
        # Verify specific results
        search_a, search_b, summary, draft = results
        assert search_a.data["query"] == "project A"
        assert search_b.data["query"] == "project B"
        assert len(summary.data["summaries"]) == 1
        assert draft.data["is_reply"] is False