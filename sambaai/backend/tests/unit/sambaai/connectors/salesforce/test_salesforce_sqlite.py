import csv
import os
import shutil
import tempfile

from sambaai.connectors.salesforce.sqlite_functions import SambaAISalesforceSQLite

_VALID_SALESFORCE_IDS = [
    "001bm00000fd9Z3AAI",
    "001bm00000fdYTdAAM",
    "001bm00000fdYTeAAM",
    "001bm00000fdYTfAAM",
    "001bm00000fdYTgAAM",
    "001bm00000fdYThAAM",
    "001bm00000fdYTiAAM",
    "001bm00000fdYTjAAM",
    "001bm00000fdYTkAAM",
    "001bm00000fdYTlAAM",
    "001bm00000fdYTmAAM",
    "001bm00000fdYTnAAM",
    "001bm00000fdYToAAM",
    "500bm00000XoOxtAAF",
    "500bm00000XoOxuAAF",
    "500bm00000XoOxvAAF",
    "500bm00000XoOxwAAF",
    "500bm00000XoOxxAAF",
    "500bm00000XoOxyAAF",
    "500bm00000XoOxzAAF",
    "500bm00000XoOy0AAF",
    "500bm00000XoOy1AAF",
    "500bm00000XoOy2AAF",
    "500bm00000XoOy3AAF",
    "500bm00000XoOy4AAF",
    "500bm00000XoOy5AAF",
    "500bm00000XoOy6AAF",
    "500bm00000XoOy7AAF",
    "500bm00000XoOy8AAF",
    "500bm00000XoOy9AAF",
    "500bm00000XoOyAAAV",
    "500bm00000XoOyBAAV",
    "500bm00000XoOyCAAV",
    "500bm00000XoOyDAAV",
    "500bm00000XoOyEAAV",
    "500bm00000XoOyFAAV",
    "500bm00000XoOyGAAV",
    "500bm00000XoOyHAAV",
    "500bm00000XoOyIAAV",
    "003bm00000EjHCjAAN",
    "003bm00000EjHCkAAN",
    "003bm00000EjHClAAN",
    "003bm00000EjHCmAAN",
    "003bm00000EjHCnAAN",
    "003bm00000EjHCoAAN",
    "003bm00000EjHCpAAN",
    "003bm00000EjHCqAAN",
    "003bm00000EjHCrAAN",
    "003bm00000EjHCsAAN",
    "003bm00000EjHCtAAN",
    "003bm00000EjHCuAAN",
    "003bm00000EjHCvAAN",
    "003bm00000EjHCwAAN",
    "003bm00000EjHCxAAN",
    "003bm00000EjHCyAAN",
    "003bm00000EjHCzAAN",
    "003bm00000EjHD0AAN",
    "003bm00000EjHD1AAN",
    "003bm00000EjHD2AAN",
    "550bm00000EXc2tAAD",
    "006bm000006kyDpAAI",
    "006bm000006kyDqAAI",
    "006bm000006kyDrAAI",
    "006bm000006kyDsAAI",
    "006bm000006kyDtAAI",
    "006bm000006kyDuAAI",
    "006bm000006kyDvAAI",
    "006bm000006kyDwAAI",
    "006bm000006kyDxAAI",
    "006bm000006kyDyAAI",
    "006bm000006kyDzAAI",
    "006bm000006kyE0AAI",
    "006bm000006kyE1AAI",
    "006bm000006kyE2AAI",
    "006bm000006kyE3AAI",
    "006bm000006kyE4AAI",
    "006bm000006kyE5AAI",
    "006bm000006kyE6AAI",
    "006bm000006kyE7AAI",
    "006bm000006kyE8AAI",
    "006bm000006kyE9AAI",
    "006bm000006kyEAAAY",
    "006bm000006kyEBAAY",
    "006bm000006kyECAAY",
    "006bm000006kyEDAAY",
    "006bm000006kyEEAAY",
    "006bm000006kyEFAAY",
    "006bm000006kyEGAAY",
    "006bm000006kyEHAAY",
    "006bm000006kyEIAAY",
    "006bm000006kyEJAAY",
    "005bm000009zy0TAAQ",
    "005bm000009zy25AAA",
    "005bm000009zy26AAA",
    "005bm000009zy28AAA",
    "005bm000009zy29AAA",
    "005bm000009zy2AAAQ",
    "005bm000009zy2BAAQ",
]


def _clear_sf_db(directory: str) -> None:
    """
    Clears the SF DB by deleting all files in the data directory.
    """
    shutil.rmtree(directory, ignore_errors=True)


def _create_csv_file_and_update_db(
    sf_db: SambaAISalesforceSQLite,
    object_type: str,
    records: list[dict],
    filename: str = "test_data.csv",
) -> None:
    """
    Creates a CSV file for the given object type and records.

    Args:
        object_type: The Salesforce object type (e.g. "Account", "Contact")
        records: List of dictionaries containing the record data
        filename: Name of the CSV file to create (default: test_data.csv)
    """
    if not records:
        return

    # Get all unique fields from records
    fields: set[str] = set()
    for record in records:
        fields.update(record.keys())
    fields = set(sorted(list(fields)))  # Sort for consistent order

    # Create CSV file
    with tempfile.TemporaryDirectory() as directory:
        csv_path = os.path.join(directory, filename)
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for record in records:
                writer.writerow(record)

        # Update the database with the CSV
        sf_db.update_from_csv(object_type, csv_path)


def _create_csv_with_example_data(sf_db: SambaAISalesforceSQLite) -> None:
    """
    Creates CSV files with example data, organized by object type.
    """
    example_data: dict[str, list[dict]] = {
        "Account": [
            {
                "Id": _VALID_SALESFORCE_IDS[0],
                "Name": "Acme Inc.",
                "BillingCity": "New York",
                "Industry": "Technology",
            },
            {
                "Id": _VALID_SALESFORCE_IDS[1],
                "Name": "Globex Corp",
                "BillingCity": "Los Angeles",
                "Industry": "Manufacturing",
            },
            {
                "Id": _VALID_SALESFORCE_IDS[2],
                "Name": "Initech",
                "BillingCity": "Austin",
                "Industry": "Software",
            },
            {
                "Id": _VALID_SALESFORCE_IDS[3],
                "Name": "TechCorp Solutions",
                "BillingCity": "San Francisco",
                "Industry": "Software",
                "AnnualRevenue": 5000000,
            },
            {
                "Id": _VALID_SALESFORCE_IDS[4],
                "Name": "BioMed Research",
                "BillingCity": "Boston",
                "Industry": "Healthcare",
                "AnnualRevenue": 12000000,
            },
            {
                "Id": _VALID_SALESFORCE_IDS[5],
                "Name": "Green Energy Co",
                "BillingCity": "Portland",
                "Industry": "Energy",
                "AnnualRevenue": 8000000,
            },
            {
                "Id": _VALID_SALESFORCE_IDS[6],
                "Name": "DataFlow Analytics",
                "BillingCity": "Seattle",
                "Industry": "Technology",
                "AnnualRevenue": 3000000,
            },
            {
                "Id": _VALID_SALESFORCE_IDS[7],
                "Name": "Cloud Nine Services",
                "BillingCity": "Denver",
                "Industry": "Cloud Computing",
                "AnnualRevenue": 7000000,
            },
        ],
        "Contact": [
            {
                "Id": _VALID_SALESFORCE_IDS[40],
                "FirstName": "John",
                "LastName": "Doe",
                "Email": "john.doe@acme.com",
                "Title": "CEO",
            },
            {
                "Id": _VALID_SALESFORCE_IDS[41],
                "FirstName": "Jane",
                "LastName": "Smith",
                "Email": "jane.smith@acme.com",
                "Title": "CTO",
            },
            {
                "Id": _VALID_SALESFORCE_IDS[42],
                "FirstName": "Bob",
                "LastName": "Johnson",
                "Email": "bob.j@globex.com",
                "Title": "Sales Director",
            },
            {
                "Id": _VALID_SALESFORCE_IDS[43],
                "FirstName": "Sarah",
                "LastName": "Chen",
                "Email": "sarah.chen@techcorp.com",
                "Title": "Product Manager",
                "Phone": "415-555-0101",
            },
            {
                "Id": _VALID_SALESFORCE_IDS[44],
                "FirstName": "Michael",
                "LastName": "Rodriguez",
                "Email": "m.rodriguez@biomed.com",
                "Title": "Research Director",
                "Phone": "617-555-0202",
            },
            {
                "Id": _VALID_SALESFORCE_IDS[45],
                "FirstName": "Emily",
                "LastName": "Green",
                "Email": "emily.g@greenenergy.com",
                "Title": "Sustainability Lead",
                "Phone": "503-555-0303",
            },
            {
                "Id": _VALID_SALESFORCE_IDS[46],
                "FirstName": "David",
                "LastName": "Kim",
                "Email": "david.kim@dataflow.com",
                "Title": "Data Scientist",
                "Phone": "206-555-0404",
            },
            {
                "Id": _VALID_SALESFORCE_IDS[47],
                "FirstName": "Rachel",
                "LastName": "Taylor",
                "Email": "r.taylor@cloudnine.com",
                "Title": "Cloud Architect",
                "Phone": "303-555-0505",
            },
        ],
        "Opportunity": [
            {
                "Id": _VALID_SALESFORCE_IDS[62],
                "Name": "Acme Server Upgrade",
                "Amount": 50000,
                "Stage": "Prospecting",
                "CloseDate": "2024-06-30",
            },
            {
                "Id": _VALID_SALESFORCE_IDS[63],
                "Name": "Globex Manufacturing Line",
                "Amount": 150000,
                "Stage": "Negotiation",
                "CloseDate": "2024-03-15",
            },
            {
                "Id": _VALID_SALESFORCE_IDS[64],
                "Name": "Initech Software License",
                "Amount": 75000,
                "Stage": "Closed Won",
                "CloseDate": "2024-01-30",
            },
            {
                "Id": _VALID_SALESFORCE_IDS[65],
                "Name": "TechCorp AI Implementation",
                "Amount": 250000,
                "Stage": "Needs Analysis",
                "CloseDate": "2024-08-15",
                "Probability": 60,
            },
            {
                "Id": _VALID_SALESFORCE_IDS[66],
                "Name": "BioMed Lab Equipment",
                "Amount": 500000,
                "Stage": "Value Proposition",
                "CloseDate": "2024-09-30",
                "Probability": 75,
            },
            {
                "Id": _VALID_SALESFORCE_IDS[67],
                "Name": "Green Energy Solar Project",
                "Amount": 750000,
                "Stage": "Proposal",
                "CloseDate": "2024-07-15",
                "Probability": 80,
            },
            {
                "Id": _VALID_SALESFORCE_IDS[68],
                "Name": "DataFlow Analytics Platform",
                "Amount": 180000,
                "Stage": "Negotiation",
                "CloseDate": "2024-05-30",
                "Probability": 90,
            },
            {
                "Id": _VALID_SALESFORCE_IDS[69],
                "Name": "Cloud Nine Infrastructure",
                "Amount": 300000,
                "Stage": "Qualification",
                "CloseDate": "2024-10-15",
                "Probability": 40,
            },
        ],
    }

    # Create CSV files for each object type
    for object_type, records in example_data.items():
        _create_csv_file_and_update_db(sf_db, object_type, records)


def _test_query(sf_db: SambaAISalesforceSQLite) -> None:
    """
    Tests querying functionality by verifying:
    1. All expected Account IDs are found
    2. Each Account's data matches what was inserted
    """
    # Expected test data for verification
    expected_accounts: dict[str, dict[str, str | int]] = {
        _VALID_SALESFORCE_IDS[0]: {
            "Name": "Acme Inc.",
            "BillingCity": "New York",
            "Industry": "Technology",
        },
        _VALID_SALESFORCE_IDS[1]: {
            "Name": "Globex Corp",
            "BillingCity": "Los Angeles",
            "Industry": "Manufacturing",
        },
        _VALID_SALESFORCE_IDS[2]: {
            "Name": "Initech",
            "BillingCity": "Austin",
            "Industry": "Software",
        },
        _VALID_SALESFORCE_IDS[3]: {
            "Name": "TechCorp Solutions",
            "BillingCity": "San Francisco",
            "Industry": "Software",
            "AnnualRevenue": 5000000,
        },
        _VALID_SALESFORCE_IDS[4]: {
            "Name": "BioMed Research",
            "BillingCity": "Boston",
            "Industry": "Healthcare",
            "AnnualRevenue": 12000000,
        },
        _VALID_SALESFORCE_IDS[5]: {
            "Name": "Green Energy Co",
            "BillingCity": "Portland",
            "Industry": "Energy",
            "AnnualRevenue": 8000000,
        },
        _VALID_SALESFORCE_IDS[6]: {
            "Name": "DataFlow Analytics",
            "BillingCity": "Seattle",
            "Industry": "Technology",
            "AnnualRevenue": 3000000,
        },
        _VALID_SALESFORCE_IDS[7]: {
            "Name": "Cloud Nine Services",
            "BillingCity": "Denver",
            "Industry": "Cloud Computing",
            "AnnualRevenue": 7000000,
        },
    }

    # Get all Account IDs
    account_ids = sf_db.find_ids_by_type("Account")

    # Verify we found all expected accounts
    assert len(account_ids) == len(
        expected_accounts
    ), f"Expected {len(expected_accounts)} accounts, found {len(account_ids)}"
    assert set(account_ids) == set(
        expected_accounts.keys()
    ), "Found account IDs don't match expected IDs"

    # Verify each account's data
    for acc_id in account_ids:
        combined = sf_db.get_record(acc_id)
        assert combined is not None, f"Could not find account {acc_id}"

        expected = expected_accounts[acc_id]

        # Verify account data matches
        for key, value in expected.items():
            value = str(value)
            assert (
                combined.data[key] == value
            ), f"Account {acc_id} field {key} expected {value}, got {combined.data[key]}"

    print("All query tests passed successfully!")


def _test_upsert(sf_db: SambaAISalesforceSQLite) -> None:
    """
    Tests upsert functionality by:
    1. Updating an existing account
    2. Creating a new account
    3. Verifying both operations were successful
    """
    # Create CSV for updating an existing account and adding a new one
    update_data: list[dict[str, str | int]] = [
        {
            "Id": _VALID_SALESFORCE_IDS[0],
            "Name": "Acme Inc. Updated",
            "BillingCity": "New York",
            "Industry": "Technology",
            "Description": "Updated company info",
        },
        {
            "Id": _VALID_SALESFORCE_IDS[2],
            "Name": "New Company Inc.",
            "BillingCity": "Miami",
            "Industry": "Finance",
            "AnnualRevenue": 1000000,
        },
    ]

    _create_csv_file_and_update_db(sf_db, "Account", update_data, "update_data.csv")

    # Verify the update worked
    updated_record = sf_db.get_record(_VALID_SALESFORCE_IDS[0])
    assert updated_record is not None, "Updated record not found"
    assert updated_record.data["Name"] == "Acme Inc. Updated", "Name not updated"
    assert (
        updated_record.data["Description"] == "Updated company info"
    ), "Description not added"

    # Verify the new record was created
    new_record = sf_db.get_record(_VALID_SALESFORCE_IDS[2])
    assert new_record is not None, "New record not found"
    assert new_record.data["Name"] == "New Company Inc.", "New record name incorrect"
    assert new_record.data["AnnualRevenue"] == "1000000", "New record revenue incorrect"

    print("All upsert tests passed successfully!")


def _test_relationships(sf_db: SambaAISalesforceSQLite) -> None:
    """
    Tests relationship shelf updates and queries by:
    1. Creating test data with relationships
    2. Verifying the relationships are correctly stored
    3. Testing relationship queries
    """
    # Create test data for each object type
    test_data: dict[str, list[dict[str, str | int]]] = {
        "Case": [
            {
                "Id": _VALID_SALESFORCE_IDS[13],
                "AccountId": _VALID_SALESFORCE_IDS[0],
                "Subject": "Test Case 1",
            },
            {
                "Id": _VALID_SALESFORCE_IDS[14],
                "AccountId": _VALID_SALESFORCE_IDS[0],
                "Subject": "Test Case 2",
            },
        ],
        "Contact": [
            {
                "Id": _VALID_SALESFORCE_IDS[48],
                "AccountId": _VALID_SALESFORCE_IDS[0],
                "FirstName": "Test",
                "LastName": "Contact",
            }
        ],
        "Opportunity": [
            {
                "Id": _VALID_SALESFORCE_IDS[62],
                "AccountId": _VALID_SALESFORCE_IDS[0],
                "Name": "Test Opportunity",
                "Amount": 100000,
            }
        ],
    }

    # Create and update CSV files for each object type
    for object_type, records in test_data.items():
        _create_csv_file_and_update_db(
            sf_db, object_type, records, "relationship_test.csv"
        )

    # Test relationship queries
    # All these objects should be children of Acme Inc.
    child_ids = sf_db.get_child_ids(_VALID_SALESFORCE_IDS[0])
    assert len(child_ids) == 4, f"Expected 4 child objects, found {len(child_ids)}"
    assert _VALID_SALESFORCE_IDS[13] in child_ids, "Case 1 not found in relationship"
    assert _VALID_SALESFORCE_IDS[14] in child_ids, "Case 2 not found in relationship"
    assert _VALID_SALESFORCE_IDS[48] in child_ids, "Contact not found in relationship"
    assert (
        _VALID_SALESFORCE_IDS[62] in child_ids
    ), "Opportunity not found in relationship"

    # Test querying relationships for a different account (should be empty)
    other_account_children = sf_db.get_child_ids(_VALID_SALESFORCE_IDS[1])
    assert (
        len(other_account_children) == 0
    ), "Expected no children for different account"

    print("All relationship tests passed successfully!")


def _test_account_with_children(sf_db: SambaAISalesforceSQLite) -> None:
    """
    Tests querying all accounts and retrieving their child objects.
    This test verifies that:
    1. All accounts can be retrieved
    2. Child objects are correctly linked
    3. Child object data is complete and accurate
    """
    # First get all account IDs
    account_ids = sf_db.find_ids_by_type("Account")
    assert len(account_ids) > 0, "No accounts found"

    # For each account, get its children and verify the data
    for account_id in account_ids:
        account = sf_db.get_record(account_id)
        assert account is not None, f"Could not find account {account_id}"

        # Get all child objects
        child_ids = sf_db.get_child_ids(account_id)

        # For Acme Inc., verify specific relationships
        if account_id == _VALID_SALESFORCE_IDS[0]:  # Acme Inc.
            assert (
                len(child_ids) == 4
            ), f"Expected 4 children for Acme Inc., found {len(child_ids)}"

            # Get all child records
            child_records = []
            for child_id in child_ids:
                child_record = sf_db.get_record(child_id)
                if child_record is not None:
                    child_records.append(child_record)
            # Verify Cases
            cases = [r for r in child_records if r.type == "Case"]
            assert (
                len(cases) == 2
            ), f"Expected 2 cases for Acme Inc., found {len(cases)}"
            case_subjects = {case.data["Subject"] for case in cases}
            assert "Test Case 1" in case_subjects, "Test Case 1 not found"
            assert "Test Case 2" in case_subjects, "Test Case 2 not found"

            # Verify Contacts
            contacts = [r for r in child_records if r.type == "Contact"]
            assert (
                len(contacts) == 1
            ), f"Expected 1 contact for Acme Inc., found {len(contacts)}"
            contact = contacts[0]
            assert contact.data["FirstName"] == "Test", "Contact first name mismatch"
            assert contact.data["LastName"] == "Contact", "Contact last name mismatch"

            # Verify Opportunities
            opportunities = [r for r in child_records if r.type == "Opportunity"]
            assert (
                len(opportunities) == 1
            ), f"Expected 1 opportunity for Acme Inc., found {len(opportunities)}"
            opportunity = opportunities[0]
            assert (
                opportunity.data["Name"] == "Test Opportunity"
            ), "Opportunity name mismatch"
            assert opportunity.data["Amount"] == "100000", "Opportunity amount mismatch"

    print("All account with children tests passed successfully!")


def _test_relationship_updates(sf_db: SambaAISalesforceSQLite) -> None:
    """
    Tests that relationships are properly updated when a child object's parent reference changes.
    This test verifies:
    1. Initial relationship is created correctly
    2. When parent reference is updated, old relationship is removed
    3. New relationship is created correctly
    """
    # Create initial test data - Contact linked to Acme Inc.
    initial_contact = [
        {
            "Id": _VALID_SALESFORCE_IDS[40],
            "AccountId": _VALID_SALESFORCE_IDS[0],
            "FirstName": "Test",
            "LastName": "Contact",
        }
    ]
    _create_csv_file_and_update_db(
        sf_db, "Contact", initial_contact, "initial_contact.csv"
    )

    # Verify initial relationship
    acme_children = sf_db.get_child_ids(_VALID_SALESFORCE_IDS[0])
    assert (
        _VALID_SALESFORCE_IDS[40] in acme_children
    ), "Initial relationship not created"

    # Update contact to be linked to Globex Corp instead
    updated_contact = [
        {
            "Id": _VALID_SALESFORCE_IDS[40],
            "AccountId": _VALID_SALESFORCE_IDS[1],
            "FirstName": "Test",
            "LastName": "Contact",
        }
    ]
    _create_csv_file_and_update_db(
        sf_db, "Contact", updated_contact, "updated_contact.csv"
    )

    # Verify old relationship is removed
    acme_children = sf_db.get_child_ids(_VALID_SALESFORCE_IDS[0])
    assert (
        _VALID_SALESFORCE_IDS[40] not in acme_children
    ), "Old relationship not removed"

    # Verify new relationship is created
    globex_children = sf_db.get_child_ids(_VALID_SALESFORCE_IDS[1])
    assert _VALID_SALESFORCE_IDS[40] in globex_children, "New relationship not created"

    print("All relationship update tests passed successfully!")


def _test_get_affected_parent_ids(sf_db: SambaAISalesforceSQLite) -> None:
    """
    Tests get_affected_parent_ids functionality by verifying:
    1. IDs that are directly in the parent_types list are included
    2. IDs that have children in the updated_ids list are included
    3. IDs that are neither of the above are not included
    """
    # Create test data with relationships
    test_data = {
        "Account": [
            {
                "Id": _VALID_SALESFORCE_IDS[0],
                "Name": "Parent Account 1",
            },
            {
                "Id": _VALID_SALESFORCE_IDS[1],
                "Name": "Parent Account 2",
            },
            {
                "Id": _VALID_SALESFORCE_IDS[2],
                "Name": "Not Affected Account",
            },
        ],
        "Contact": [
            {
                "Id": _VALID_SALESFORCE_IDS[40],
                "AccountId": _VALID_SALESFORCE_IDS[0],
                "FirstName": "Child",
                "LastName": "Contact",
            }
        ],
    }

    # Create and update CSV files for test data
    for object_type, records in test_data.items():
        _create_csv_file_and_update_db(sf_db, object_type, records)

    # Test Case 1: Account directly in updated_ids and parent_types
    updated_ids = [_VALID_SALESFORCE_IDS[1]]  # Parent Account 2
    parent_types = ["Account"]
    affected_ids_by_type = dict(
        sf_db.get_affected_parent_ids_by_type(updated_ids, parent_types)
    )
    assert "Account" in affected_ids_by_type, "Account type not in affected_ids_by_type"
    assert (
        _VALID_SALESFORCE_IDS[1] in affected_ids_by_type["Account"]
    ), "Direct parent ID not included"

    # Test Case 2: Account with child in updated_ids
    updated_ids = [_VALID_SALESFORCE_IDS[40]]  # Child Contact
    parent_types = ["Account"]
    affected_ids_by_type = dict(
        sf_db.get_affected_parent_ids_by_type(updated_ids, parent_types)
    )
    assert "Account" in affected_ids_by_type, "Account type not in affected_ids_by_type"
    assert (
        _VALID_SALESFORCE_IDS[0] in affected_ids_by_type["Account"]
    ), "Parent of updated child not included"

    # Test Case 3: Both direct and indirect affects
    updated_ids = [_VALID_SALESFORCE_IDS[1], _VALID_SALESFORCE_IDS[40]]  # Both cases
    parent_types = ["Account"]
    affected_ids_by_type = dict(
        sf_db.get_affected_parent_ids_by_type(updated_ids, parent_types)
    )
    assert "Account" in affected_ids_by_type, "Account type not in affected_ids_by_type"
    affected_ids = affected_ids_by_type["Account"]
    assert len(affected_ids) == 2, "Expected exactly two affected parent IDs"
    assert _VALID_SALESFORCE_IDS[0] in affected_ids, "Parent of child not included"
    assert _VALID_SALESFORCE_IDS[1] in affected_ids, "Direct parent ID not included"
    assert (
        _VALID_SALESFORCE_IDS[2] not in affected_ids
    ), "Unaffected ID incorrectly included"

    # Test Case 4: No matches
    updated_ids = [_VALID_SALESFORCE_IDS[40]]  # Child Contact
    parent_types = ["Opportunity"]  # Wrong type
    affected_ids_by_type = dict(
        sf_db.get_affected_parent_ids_by_type(updated_ids, parent_types)
    )
    assert len(affected_ids_by_type) == 0, "Should return empty dict when no matches"

    print("All get_affected_parent_ids tests passed successfully!")


def test_salesforce_sqlite() -> None:
    with tempfile.TemporaryDirectory() as directory:
        _clear_sf_db(directory)

        filename = os.path.join(directory, "salesforce_db.sqlite")
        sf_db = SambaAISalesforceSQLite(filename)
        sf_db.connect()
        sf_db.apply_schema()

        _create_csv_with_example_data(sf_db)
        _test_query(sf_db)
        _test_upsert(sf_db)
        _test_relationships(sf_db)
        _test_account_with_children(sf_db)
        _test_relationship_updates(sf_db)
        _test_get_affected_parent_ids(sf_db)

        sf_db.close()

        _clear_sf_db(directory)
