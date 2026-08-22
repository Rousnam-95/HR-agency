from leadgen.enrich.schema import Contact


def test_blank_contact_is_valid_no_errors():
    contact = Contact.from_raw({})
    assert contact.validate() == []


def test_named_contact_with_email_is_valid():
    contact = Contact.from_raw({
        "contact_name": "Julie Tremblay", "contact_title": "Directrice RH",
        "contact_email": "j.tremblay@example.com", "contact_source_tier": "company_site",
        "contact_confidence": "High",
    })
    assert contact.validate() == []


def test_generic_fallback_must_be_tagged_low_confidence():
    contact = Contact.from_raw({
        "contact_email": "info@example.com", "contact_source_tier": "generic_fallback",
        "contact_confidence": "High",
    })
    errors = contact.validate()
    assert any("confidence=Low" in e for e in errors)


def test_source_tier_without_email_or_phone_is_flagged():
    contact = Contact.from_raw({
        "contact_name": "Julie Tremblay", "contact_source_tier": "linkedin_search",
        "contact_confidence": "Medium",
    })
    errors = contact.validate()
    assert any("no email or phone" in e for e in errors)


def test_named_tier_without_a_name_is_flagged():
    contact = Contact.from_raw({
        "contact_email": "j.t@example.com", "contact_source_tier": "req_registry",
        "contact_confidence": "High",
    })
    errors = contact.validate()
    assert any("contact_name is blank" in e for e in errors)


def test_invalid_enum_values_are_flagged():
    contact = Contact.from_raw({"contact_source_tier": "made_up", "contact_confidence": "Sure"})
    errors = contact.validate()
    assert any("invalid contact_source_tier" in e for e in errors)
    assert any("invalid contact_confidence" in e for e in errors)
