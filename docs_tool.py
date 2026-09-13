"""
docs_tool.py - Google Docs Tool

Provides a single-purpose function to append text content to the end of
a Google Doc using the Google Docs API (v1) batchUpdate method.
It also supports creating a new document if doc_id is empty.
"""

from auth import build_service


def append_to_doc(doc_id: str, content: str, title: str = "Untitled Document") -> dict:
    """
    Append the given text content to the end of the specified Google Doc.

    Internal flow:
      1. Build an authenticated Google Docs service.
      2. If doc_id is empty, create a new document with the given title.
      3. Retrieve the current document to find the end-of-body index.
      4. Construct a batchUpdate request with an InsertTextRequest
         targeting the end-of-body location.
      5. Execute the request and return the response metadata.

    Args:
        doc_id:  The unique identifier of the Google Doc
                 (found in the document URL). If empty, creates new doc.
        content: The text string to append to the document.
        title:   The title to use if creating a new document.

    Returns:
        A dict containing:
          - status: "success" or "error"
          - message: Human-readable result description
          - doc_id: The document ID that was modified
          - doc_url: The URL of the document
          - api_response: Raw API response (on success)

    Raises:
        googleapiclient.errors.HttpError: If the Docs API call fails.
    """
    service = build_service("docs", "v1")

    # If no doc_id is provided, create a new document
    if not doc_id:
        document = service.documents().create(body={"title": title}).execute()
        doc_id = document.get("documentId")

    # Retrieve the document to determine the end-of-body index.
    # The body content ends at endIndex - 1 (the last '\n' occupies that slot).
    document = service.documents().get(documentId=doc_id).execute()
    body_content = document.get("body", {}).get("content", [])

    # The end index of the body is the last structural element's endIndex.
    # We insert at endIndex - 1 to place text before the final newline.
    end_index = 1  # fallback: beginning of doc
    if body_content:
        last_element = body_content[-1]
        end_index = last_element.get("endIndex", 1) - 1

    # Ensure we don't insert at index 0 (reserved)
    if end_index < 1:
        end_index = 1

    # Build the batchUpdate request
    requests = [
        {
            "insertText": {
                "location": {"index": end_index},
                "text": content,
            }
        }
    ]

    response = (
        service.documents()
        .batchUpdate(documentId=doc_id, body={"requests": requests})
        .execute()
    )

    return {
        "status": "success",
        "message": "Content appended to document.",
        "doc_id": doc_id,
        "doc_url": f"https://docs.google.com/document/d/{doc_id}/edit",
        "api_response": response,
    }
