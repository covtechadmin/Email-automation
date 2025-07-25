import os

def clean_payload(payload: dict) -> dict:
    """Clean payload for Perplexity API: remove unsupported fields and fix booleans."""
    cleaned = dict(payload)
    # Remove unsupported fields
    for key in ["return_images", "return_related_questions", "stream"]:
        cleaned.pop(key, None)
    # Convert Python bools to JSON bools (True/False to true/false)
    for k, v in cleaned.items():
        if isinstance(v, bool):
            cleaned[k] = bool(v)
    # Recursively clean nested dicts/lists
    for k, v in cleaned.items():
        if isinstance(v, dict):
            cleaned[k] = clean_payload(v)
        elif isinstance(v, list):
            cleaned[k] = [clean_payload(i) if isinstance(i, dict) else i for i in v]
    return cleaned
import pandas as pd
import streamlit as st
import requests
import json
import os
from typing import Iterator
import io

# Page configuration
st.set_page_config(
    page_title="B2B Lead Generation Chatbot",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# API Configuration
PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"

# Services configuration with corresponding value propositions and pain points
SERVICES_CONFIG = {
    "Chiral synthesis": {
        "description": "Production of enantiomerically pure compounds",
        "value_proposition": "We deliver 99%+ enantiomeric excess in chiral synthesis with proprietary asymmetric catalysis, reducing development timelines by 40% and ensuring regulatory compliance for pharmaceutical APIs",
        "pain_points": "Enantiomeric impurities causing regulatory failures, high development costs for chiral separation, scalability challenges from lab to commercial production",
        "keywords": ["chiral synthesis", "asymmetric catalysis", "enantiomeric excess", "optical purity", "stereochemistry"]
    },
    "Fluorination": {
        "description": "Introduction of fluorine atoms into organic molecules",
        "value_proposition": "We provide selective fluorination chemistry with 95%+ regioselectivity using advanced fluorinating agents, enhancing drug bioavailability and metabolic stability",
        "pain_points": "Safety concerns with fluorinating reagents, poor regioselectivity leading to byproducts, lack of specialized fluorine chemistry expertise",
        "keywords": ["fluorination", "fluorinating agents", "organofluorine", "selective fluorination", "fluorine chemistry"]
    },
    "Isotopic labeling (D₂O)": {
        "description": "Incorporation of deuterium for research/analytical purposes",
        "value_proposition": "We offer comprehensive deuterium labeling services with 98%+ isotopic purity, enabling precise metabolic studies and extending drug patent life",
        "pain_points": "High costs of deuterated reagents, isotope exchange during synthesis, analytical challenges in quantifying deuterium incorporation",
        "keywords": ["deuterium labeling", "isotopic labeling", "deuterated compounds", "metabolic studies", "isotope chemistry"]
    },
    "Cryogenic reactions (-80°C)": {
        "description": "Low-temperature synthetic processes",
        "value_proposition": "We execute ultra-low temperature chemistry down to -80°C with precise temperature control, enabling thermally sensitive reactions and unique selectivity",
        "pain_points": "Equipment costs for cryogenic operations, safety risks at extreme temperatures, energy consumption and operational complexity",
        "keywords": ["cryogenic reactions", "low temperature synthesis", "ultra-cold chemistry", "temperature control", "specialized equipment"]
    },
    "Phosgenation": {
        "description": "Reactions involving phosgene chemistry",
        "value_proposition": "We safely handle phosgene chemistry with specialized containment systems and trained personnel, delivering high-purity carbonyl compounds with zero safety incidents",
        "pain_points": "Extreme toxicity and safety risks of phosgene, regulatory compliance challenges, specialized equipment and training requirements",
        "keywords": ["phosgenation", "phosgene chemistry", "carbonyl compounds", "toxic gas handling", "safety protocols"]
    },
    "DoE-led development and scale-up": {
        "description": "Design of Experiments methodology for process optimization from grams to commercial batches",
        "value_proposition": "We use statistical DoE methodology to optimize processes with 50% fewer experiments, ensuring seamless scale-up from grams to tons with predictable outcomes",
        "pain_points": "Scale-up failures from lab to production, inefficient trial-and-error optimization, lack of statistical process understanding",
        "keywords": ["design of experiments", "process optimization", "scale-up", "statistical analysis", "process development"]
    },
    "Cryogenic capability (nBuLi, LAH, Grignard)": {
        "description": "nBuLi, LAH, and Grignard reagent chemistry",
        "value_proposition": "We handle highly reactive organometallic reagents with specialized inert atmosphere systems, achieving 95%+ yields in moisture-sensitive transformations",
        "pain_points": "Moisture sensitivity requiring inert conditions, safety risks with pyrophoric reagents, specialized handling and storage requirements",
        "keywords": ["organometallic chemistry", "Grignard reagents", "lithium reagents", "inert atmosphere", "pyrophoric handling"]
    },
    "Hydrogenation services": {
        "description": "Multi-scale capabilities: 25L (1400psi), 100L (1400psi), and 3000L (700psi)",
        "value_proposition": "We provide multi-scale hydrogenation from 25L to 3000L with pressure capabilities up to 1400psi, ensuring consistent selectivity and safety across all scales",
        "pain_points": "High pressure safety risks, catalyst optimization challenges, scale-dependent selectivity issues, specialized pressure equipment costs",
        "keywords": ["hydrogenation", "high pressure reactions", "catalytic reduction", "pressure vessels", "catalyst screening"]
    },
    "Solvent recovery": {
        "description": "Purification and recycling of process solvents",
        "value_proposition": "We provide solvent recovery solutions that reduce waste disposal costs by 70% and ensure environmental compliance with 99%+ purity recovery rates",
        "pain_points": "High waste disposal costs, environmental compliance issues, solvent purchasing expenses, sustainability pressure",
        "keywords": ["solvent recovery", "solvent recycling", "waste reduction", "environmental compliance", "cost reduction"]
    },
    "Advanced Materials": {
        "description": "Specialty chemical manufacturing",
        "value_proposition": "We manufacture high-performance specialty chemicals with precise specifications, enabling breakthrough material properties and reducing time-to-market by 30%",
        "pain_points": "Stringent quality specifications, scalability from R&D to production, supply chain reliability for critical materials",
        "keywords": ["advanced materials", "specialty chemicals", "high performance materials", "custom synthesis", "material properties"]
    },
    "Home and Personal Care": {
        "description": "Consumer product ingredients",
        "value_proposition": "We develop consumer-safe ingredients with natural origins and sustainable processes, meeting clean beauty trends while maintaining performance efficacy",
        "pain_points": "Consumer safety and regulatory compliance, sustainable sourcing pressure, performance vs. natural ingredient balance",
        "keywords": ["personal care ingredients", "consumer safety", "natural ingredients", "cosmetic chemistry", "sustainable beauty"]
    },
    "Agrochemicals": {
        "description": "Crop protection and agricultural chemicals",
        "value_proposition": "We synthesize crop protection intermediates with 99%+ purity and environmental safety profiles, supporting food security while minimizing ecological impact",
        "pain_points": "Environmental impact regulations, resistance development in target pests, registration costs and timelines for new actives",
        "keywords": ["agrochemicals", "crop protection", "pesticide intermediates", "agricultural chemistry", "environmental safety"]
    },
    "Pharmaceuticals": {
        "description": "Drug intermediates and APIs",
        "value_proposition": "We manufacture pharmaceutical intermediates and APIs under cGMP compliance with 99.9%+ purity, ensuring regulatory approval and patient safety",
        "pain_points": "Regulatory compliance and documentation requirements, impurity control and analytical challenges, supply chain security and continuity",
        "keywords": ["pharmaceutical intermediates", "API manufacturing", "cGMP compliance", "drug development", "regulatory approval"]
    }
}

def stream_perplexity_response(payload: dict) -> Iterator[str]:
    """Stream response from Perplexity API"""
    api_key = st.session_state.get("PERPLEXITY_API_KEY", os.getenv("PERPLEXITY_API_KEY", "your-perplexity-api-key-here"))
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    try:
        cleaned_payload = clean_payload(payload)
        response = requests.post(
            PERPLEXITY_API_URL,
            headers=headers,
            json=cleaned_payload,
            stream=True
        )
        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            error_msg = f"API Error: {e}\nStatus Code: {response.status_code}\nResponse: {response.text}"
            yield f"\n**API Error:**\n\n{error_msg}\n"
            return 
        yield response.text
    except requests.RequestException as e:
        error_msg = f"Request Exception: {str(e)}"
        yield f"\n**Request Exception:**\n\n{error_msg}\n"

def generate_content(contact_data, sender_company, sender_name, value_proposition, pain_point, cta, content_type, selected_service, geography=None):
    """Generate different types of content using Perplexity API"""
    
    # Extract contact details from the selected row
    company_name = contact_data.get("Company Name", "")
    contact_full_name = contact_data.get("Contact Person & Title", "")
    contact_name = contact_full_name.split(" & ")[0].strip() if " & " in contact_full_name else contact_full_name.split(",")[0].strip()
    contact_title = contact_full_name.split(" & ")[1].strip() if " & " in contact_full_name else ""
    industry = contact_data.get("Industry Vertical", "")
    location = contact_data.get("Location (State)", "")
    
    if content_type == "Generate Personalized Email":
        # Determine search strategy based on geography
        if geography == "China":
            search_prompt = f"""
Search using both Baidu and Google with these queries to find professional information about {contact_name}:

**Baidu Search Queries:**
1. "{contact_name}" "{company_name}" {industry}
2. "{contact_name}" 职位 {company_name}
3. "{contact_name}" {selected_service.lower()} 专业
4. "{contact_name}" "{company_name}" 高管
5. "{contact_name}" {company_name} 管理层

**Google Backup Queries:**
1. site:linkedin.com "{contact_name}" "{company_name}"
2. "{contact_name}" {company_name} {industry} professional
3. "{contact_name}" {selected_service.lower()} expertise
4. "{contact_name}" "{company_name}" Google search
5. "{contact_name}" {company_name} executive profile

**Enhanced Fallback Searches:**
1. "{company_name}" "{contact_name}" management team
2. "{contact_name}" {industry} China professional
3. "{company_name}" leadership {industry} China
4. "{contact_name}" {company_name} news announcement

From the search results, extract professional insights such as:
• Current role and responsibilities at {company_name}
• Industry experience and expertise areas
• Recent company developments or industry involvement
• Educational background or certifications
• Any mentions of {selected_service.lower()} or {industry} challenges
• Company context and organizational structure
• Professional background and career progression

Provide actionable insights for personalized outreach, focusing on their professional background and company context. If specific personal details are limited, focus on company role and industry expertise.
""".strip()
        else:
            search_prompt = f"""
Search using Google and professional networks with these queries:

**Primary Google Queries:**
1. site:linkedin.com "{contact_name}" "{company_name}"
2. "{contact_name}" {company_name} {industry} professional
3. "{contact_name}" {selected_service.lower()} expertise
4. "{company_name}" {contact_name} news press release

**Enhanced Fallback Searches (if LinkedIn data is insufficient):**
1. "{contact_name}" "{company_name}" Google search
2. "{contact_name}" {industry} conference speaker
3. "{contact_name}" {company_name} interview article
4. "{contact_name}" {selected_service.lower()} publication
5. "{contact_name}" "{company_name}" executive profile
6. "{contact_name}" {company_name} management team
7. "{contact_name}" {industry} expert professional

**Company Context Searches:**
1. "{company_name}" leadership team {industry}
2. "{company_name}" executives management
3. "{company_name}" {industry} department heads

From the search results, extract:
• Current role tenure and key responsibilities at {company_name}
• Recent professional posts, articles, or activity (last 60 days)
• Educational background and industry certifications
• Any mentions of {selected_service.lower()}, {industry} challenges, or related projects
• Professional interests and company developments they've shared
• Company context and organizational structure
• Industry involvement and expertise areas

Provide 3-4 specific insights that can be used for personalized email outreach. If LinkedIn data is limited, focus on company context and industry expertise.
""".strip()
        
        # Get enhanced professional research
        research_payload = {
            "model": "sonar-pro",
            "messages": [{"role": "user", "content": search_prompt}],
            "max_tokens": 600,
            "temperature": 0.2
        }
        
        try:
            research_chunks = list(stream_perplexity_response(research_payload))
            research_response = "".join(str(chunk) for chunk in research_chunks)
            research_json = json.loads(research_response)
            professional_insights = research_json["choices"][0]["message"]["content"]
        except:
            professional_insights = f"Experienced {industry} professional in {contact_title} role at {company_name}, likely involved in {selected_service.lower()} decision-making processes."
        
        # Now craft email using enhanced professional insights
        prompt = f"""
Write a compelling B2B sales email to {contact_name} at {company_name}:

**PROFESSIONAL RESEARCH FINDINGS:** 
{professional_insights}

**EMAIL STRUCTURE:**
• **Greeting**: "Hi {contact_name}," 
• **Industry Opening**: Start with relevant {industry} industry insight or trend that affects {company_name}
• **Company Connection**: Reference {company_name}'s position in {industry} or recent company developments
• **Value Bridge**: Connect industry challenges to how {sender_company} addresses {selected_service.lower()} needs: {value_proposition}
• **Call to Action**: {cta}

**WRITING GUIDELINES:**
- Maximum 90 words total
- Focus on industry expertise and company relevance rather than personal details
- Professional yet conversational tone
- Industry-specific terminology for {industry}
- Location context if relevant: {location}
- Never mention inability to find personal information

**CONTENT REQUIREMENTS:**
- Lead with industry insight that's relevant to their role
- Show understanding of {company_name}'s business needs
- Demonstrate expertise in {selected_service.lower()} services
- Create value-focused connection rather than personal connection

Make the email feel professionally researched and industry-focused.
""".strip()
    
    elif content_type == "Generate Contact Profile":
        prompt = f"""
Create a brief contact profile for {contact_name} at {company_name}:

**GOOGLE LINKEDIN SEARCH:**
Search Google with: site:linkedin.com "{contact_name}" "{company_name}" to find:
• LinkedIn profile URL and current position details
• Professional experience and career progression
• Recent activity, posts, or professional updates
• Educational background and certifications
• Industry connections and endorsements

**ENHANCED PROFILE RESEARCH:**
Also search: "{contact_name}" {industry} to discover:
• Industry expertise and thought leadership
• Speaking engagements or conference participation
• Published articles or professional insights
• Company announcements they've shared or commented on

**QUICK ACTIONABLE INSIGHTS:**
• **Authority Level**: {contact_title} - decision-making scope for {selected_service.lower()} services
• **Communication Style**: Professional tone based on LinkedIn activity patterns
• **Current Focus**: Recent posts about {industry} challenges or {company_name} developments
• **Best Approach**: Optimal engagement strategy based on their professional interests

**KEY CONVERSATION STARTERS:**
• Recent company milestones or achievements they've posted about
• Industry trends or challenges they've discussed
• Professional background that connects to {selected_service.lower()} needs

Format as 4-5 bullet points maximum. Include LinkedIn profile insights and specific conversation hooks for immediate outreach.
""".strip()

    else:  # Sales Company Profile
        prompt = f"""
Create a strategic sales intelligence report for {company_name} targeting {sender_company}'s {selected_service.lower()} services:

**ENHANCED COMPANY RESEARCH:**
Perform Google searches:
1. site:linkedin.com "{company_name}" company page
2. "{company_name}" {industry} {selected_service.lower()} news
3. "{company_name}" outsourcing pharmaceutical services
4. site:linkedin.com "{company_name}" employees {industry}

**COMPANY OVERVIEW:**
Research {company_name} and provide:
• Business summary with current scale and market position
• Primary {industry} operations requiring {selected_service.lower()} services
• Recent LinkedIn company updates, funding announcements, or expansion news
• Employee insights from LinkedIn showing R&D or procurement team growth

**OPPORTUNITY ASSESSMENT:**
• Specific {selected_service.lower()} pain points based on their {industry} focus
• Technical capabilities they likely outsource vs. keep in-house
• Budget capacity indicators from recent business developments
• Competitive landscape and current service provider relationships

**LINKEDIN INTELLIGENCE:**
• Key decision-makers visible on company LinkedIn page
• Recent employee hires in R&D, procurement, or operations roles
• Company posts about growth, partnerships, or technical challenges
• Employee posts discussing {industry} or {selected_service.lower()} topics

**SALES STRATEGY:**
• Value propositions aligned with their LinkedIn-evident business priorities
• Entry strategy (technical presentation, case study, pilot project)
• Key stakeholders beyond primary contact who influence decisions

**IMMEDIATE ACTIONS:**
• LinkedIn research tasks for additional contacts
• Meeting agenda based on their current business focus
• Follow-up sequence aligned with their procurement patterns

Focus on LinkedIn-verified intelligence and current business developments for {selected_service.lower()} services opportunities.
""".strip()

    payload = {
        "model": "sonar-pro",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 1500,
        "temperature": 0.2
    }
    
    try:
        content_chunks = list(stream_perplexity_response(payload))
        content_response = "".join(str(chunk) for chunk in content_chunks)
        content_json = json.loads(content_response)
        content_text = content_json["choices"][0]["message"]["content"]
        return content_text
    except Exception as e:
        return f"Error generating {content_type.lower()}: {str(e)}"

def simple_extract_table(response_json):
    """
    Simple function to extract table from your API response
    """
    # Get the table content from the response
    table_content = response_json['choices'][0]['message']['content']
    
    # Split into lines and filter for table rows
    lines = table_content.strip().split('\n')
    table_lines = [line for line in lines if '|' in line and not line.strip().startswith('|---')]
    
    if len(table_lines) < 2:
        return None
    
    # Extract headers and data
    headers = [col.strip() for col in table_lines[0].split('|') if col.strip()]
    
    rows = []
    for line in table_lines[1:]:  # Skip header line
        row = [col.strip() for col in line.split('|') if col.strip()]
        if len(row) == len(headers):
            rows.append(row)
    
    # Create DataFrame
    df = pd.DataFrame(rows, columns=headers)
    return df

def get_default_payload(selected_service):
    """Get the default payload with service-specific configuration"""
    service_config = SERVICES_CONFIG[selected_service]
    service_keywords = service_config['keywords']
    
    # Create service-specific keyword combinations
    keyword_combinations = []
    for keyword in service_keywords:
        keyword_combinations.extend([
            f'"{keyword} service provider"',
            f'"{keyword} contract manufacturing"',
            f'"{keyword} outsourcing"',
            f'"{keyword} custom synthesis"'
        ])
    
    keyword_string = ", ".join(keyword_combinations)
    return {
  "model": "sonar-pro",
  "messages": [
    {
      "role": "system",
      "content": f"You are an elite B2B lead researcher with 10+ years specializing in global chemical manufacturing and pharmaceutical services, with deep expertise in {selected_service.lower()}, {', '.join(SERVICES_CONFIG[selected_service]['keywords'][:3])}, and international regulatory frameworks.\n\n🎯 MISSION: Identify verified, high-conversion prospects with active {selected_service.lower()} service purchasing intent, confirmed buying authority, and immediate project timelines across target geographies.\n\n📊 REAL-TIME RESEARCH METHODOLOGY:\n\n**Primary Research Channels (70% of leads):**\n• B2B Platforms: Research current active platforms in target geography for pharmaceutical/chemical outsourcing\n• Live RFQs: Active service requirements, technical specifications posted ≤60 days\n• Qualification: Verified business profiles, specific {selected_service.lower()} requirements, budget indicators\n\n**Professional Networks (20%):**\n• LinkedIn: R&D managers, procurement directors posting {selected_service.lower()} needs\n• Company updates: Recent hiring for relevant technical roles (indicates active projects)\n• Industry networks: Current member activity, conference participation\n\n**Market Intelligence (10%):**\n• Trade publications: Recent outsourcing announcements, partnership news\n• Regulatory updates: Current compliance requirements affecting {selected_service.lower()}\n• Business news: Funding rounds, R&D investments, facility developments\n\n🔍 DYNAMIC KEYWORD STRATEGY:\n\n**Service-Specific High-Intent:**\n• \"{selected_service.lower()} service provider [geography]\"\n• \"{selected_service.lower()} contract manufacturing RFQ\"\n• \"{selected_service.lower()} outsourcing partner [capacity]\"\n• \"pharmaceutical {selected_service.lower()} services\"\n\n**Technical Requirements:**\n• \"{', '.join(SERVICES_CONFIG[selected_service]['keywords'][:2])} commercial scale\"\n• \"cGMP {selected_service.lower()} manufacturing\"\n• \"API {selected_service.lower()} services\"\n• \"custom {selected_service.lower()} development\"\n\n**Pain-Point Driven:**\n• Search for companies mentioning: \"{SERVICES_CONFIG[selected_service]['pain_points']}\"\n• \"outsourcing {selected_service.lower()} to reduce costs\"\n• \"{selected_service.lower()} capacity constraints\"\n• \"regulatory compliance {selected_service.lower()}\"\n\n**Value Proposition Alignment:**\n• Target companies needing: \"{SERVICES_CONFIG[selected_service]['value_proposition']}\"\n• \"scale-up {selected_service.lower()} production\"\n• \"technology transfer {selected_service.lower()}\"\n\n✅ DYNAMIC QUALIFICATION MATRIX (Score 1-10):\n\n**IMMEDIATE PROSPECTS (9-10 points):**\n• Active RFQ with specific {selected_service.lower()} requirements\n• Budget approved or funding confirmed for {selected_service.lower()} projects\n• Implementation timeline ≤6 months\n• Direct decision-maker involvement\n• Regulatory or commercial deadline driving urgency\n\n**STRONG PROSPECTS (7-8 points):**\n• Documented {selected_service.lower()} service requirements\n• Company R&D expansion in relevant therapeutic areas\n• Previous outsourcing history in similar services\n• Technical team actively evaluating {selected_service.lower()} providers\n• Pipeline development requiring {selected_service.lower()} capabilities\n\n**QUALIFIED LEADS (5-6 points):**\n• General interest in {selected_service.lower()} services\n• Company profile matches ideal customer (pharma/biotech/chemical)\n• Revenue/funding level supports service investment\n• Geographic location within target markets\n• Some project indicators or development activity\n\n📋 ENHANCED OUTPUT TABLE FORMAT:\n\n| Qualification Score | Company Name | Contact Person & Title | Industry Vertical | Specific Solvent Requirements | Technical Specifications | Estimated Budget Range | Implementation Timeline | Decision Authority Level | Geographic Location | Direct Contact Details | Source Platform & Date | Buying Triggers | Pain Points | Business Verification | Recommended Next Actions |\n\n📝 COMPREHENSIVE DATA REQUIREMENTS:\n\n**Contact Intelligence:**\n• Full name + exact functional title (avoid generic \"Manager\")\n• Direct phone/email when available\n• LinkedIn profile verification\n• Decision-making authority level (Approver/Influencer/User)\n\n**Company Intelligence:**\n• Specific industry subsector (Pharma API, Automotive Coatings, etc.)\n• Annual revenue range with source\n• Number of employees and facilities\n• Recent business developments (expansions, acquisitions)\n\n**Technical Requirements:**\n• Specific solvents used (IPA, Acetone, MEK, Toluene, etc.)\n• Current volumes and capacity requirements\n• Purity specifications and quality standards\n• Automation level preferences\n\n**Commercial Intelligence:**\n• Budget range with confidence level\n• CAPEX cycle and approval process timeline\n• Current equipment vendor relationships\n• Competitive evaluation criteria\n\n🔄 SYSTEMATIC RESEARCH WORKFLOW:\n\n1. **Multi-Channel Search Execution:**\n   • Deploy keyword combinations across all platforms simultaneously\n   • Filter for recency (≤90 days) and geographic relevance\n   • Cross-reference company data across multiple sources\n\n2. **Business Verification Protocol:**\n   • Validate company registration via appropriate business directories\n   • Confirm operational status through recent activity indicators\n   • Verify contact authority through LinkedIn and company websites\n\n3. **Technical Requirement Analysis:**\n   • Extract specific equipment specifications from inquiries\n   • Identify capacity requirements and technical constraints\n   • Assess fit with available solution portfolio\n\n4. **Commercial Qualification:**\n   • Estimate budget capacity from company size and project scope\n   • Identify decision timeline from urgency indicators\n   • Map stakeholder influence and approval processes\n\n5. **Competitive Intelligence:**\n   • Research current vendor relationships\n   • Identify potential competitive threats\n   • Assess switching costs and barriers\n\n6. **Lead Scoring & Prioritization:**\n   • Apply qualification matrix consistently\n   • Rank by conversion probability and deal size\n   • Ensure geographic and industry diversity\n\n🚫 ENHANCED EXCLUSION CRITERIA:\n\n• Trading companies, distributors, or equipment brokers\n• Generic inquiries without specific technical requirements\n• Companies with recent major equipment installations (≤2 years)\n• Contacts without verified business email domains\n• Inquiries older than 90 days without exceptional circumstances\n• Companies below minimum revenue threshold for target solution\n• Regions with known regulatory or payment challenges\n\n� QUALITY ASSURANCE STANDARDS:\n\n• All data must be factually verifiable through source documentation\n• No assumptions or extrapolations beyond available evidence\n• Recent activity evidence required (inquiries, posts, updates ≤60 days)\n• Complete company profiles with legitimate operational presence\n• Direct manufacturing end-users only (no intermediaries)\n• Geographic compliance with target market regulations\n\nDELIVERABLE: Ranked table of qualified leads with complete intelligence profile for immediate sales execution. Include confidence levels for estimated data and mark any inferred information clearly."
    },
    {
      "role": "user",
      "content": "This will be dynamically updated based on user filters"
    }
  ],
  "search_mode": "web",
  "search_recency_filter": "month",
  "search_domain_filter": [],
  "return_images": False,
  "return_related_questions": False,
  "max_tokens": 4000,
  "temperature": 0.1,
  "top_p": 0.9
}

# Main Streamlit App
def main():
    st.title("TESTB2B")
    
    # First, get the selected service so it's available for the sidebar
    selected_service = st.selectbox(
        "Choose your service offering:",
        list(SERVICES_CONFIG.keys()),
        index=0,
        help="Select the service you want to generate leads for",
        key="main_selected_service"
    )
    st.info(f"**{selected_service}**: {SERVICES_CONFIG[selected_service]['description']}")
    
    # Sidebar for configuration - Now selected_service is available
    with st.sidebar:
        st.header("⚙️ Configuration")
        # Display service description only
        st.divider()
        st.subheader("📧 Email Settings")
        sender_company = st.text_input("Your Company Name", value="ChemTech Solutions")
        sender_name = st.text_input("Your Name", value="Nikhil Sharma")
        value_proposition = st.text_area(
            "Value Proposition", 
            value=SERVICES_CONFIG[selected_service]['value_proposition'],
            help="This is auto-populated based on your selected service"
        )
        pain_point = st.text_area(
            "Pain Points You Address", 
            value=SERVICES_CONFIG[selected_service]['pain_points'],
            help="This is auto-populated based on your selected service"
        )
        cta = st.text_input("Call to Action", value="Would you be open to a 15-minute call to discuss your current challenges and explore how our expertise can help?")
        st.divider()
        #st.success("✅ API Key is set in code.")
    
    # Main content area
    st.markdown("*AI-powered lead generation for your selected service*")
    # Lead Generation Filters in main area
    col1, col2, col3 = st.columns(3)
    with col1:
        geography = st.selectbox(
            "Target Geography",
            ["India", "China", "USA", "UAE"],
            index=0,
            key="main_geography"
        )
    with col2:
        revenue_range = st.selectbox(
            "Company Revenue Range",
            ["<$5 million", "$5 - $10 million", ">$10 million"],
            index=1,
            key="main_revenue_range"
        )
    with col3:
        num_leads = st.selectbox(
            "Number of Leads",
            [10, 15, 20],
            index=0,
            key="main_num_leads"
        )
    # st.markdown(f"*AI-powered lead generation for {selected_service.lower()} services*")
    
    # ...existing code...
    
    # Set API key directly in code
    st.session_state["PERPLEXITY_API_KEY"] = os.environ.get("PERPLEXITY_API_KEY") # <-- Set your actual API key here
    # Get default payload with selected service and apply filters
    default_payload = get_default_payload(selected_service)
    default_payload["max_tokens"] = 4000
    default_payload["temperature"] = 0.1
    default_payload["search_recency_filter"] = "month"
    if "stream" in default_payload:
        del default_payload["stream"]
    
    # Update the user message with filter parameters
    # Set geography-specific search domains and platforms
    if geography == "India":
        search_domains = ["indiamart.com", "tradeindia.com", "linkedin.com", "exportersindia.com", "chemicalweekly.com", "fibre2fashion.com", "pharmabiz.com", "justdial.com"]
        compliance_refs = "CPCB, SPCB, Hazardous Waste Rules"
        platforms = "IndiaMART/TradeIndia (50%): Recent buyer requirements with detailed technical specifications"
        currency_examples = "₹15-25 lakhs, $50-100K"
    elif geography == "China":
        search_domains = ["alibaba.com", "made-in-china.com", "linkedin.com", "globalsources.com", "chemnet.com", "chemchina.com"]
        compliance_refs = "MEE regulations, GB standards, Environmental Protection Law"
        platforms = "Alibaba/Made-in-China (50%): Recent buyer requirements with detailed technical specifications"
        currency_examples = "¥500K-2M, $80-300K"
    elif geography == "USA":
        search_domains = ["linkedin.com", "thomasnet.com", "globalspec.com", "chemweek.com", "icis.com", "chemicalprocessing.com"]
        compliance_refs = "EPA regulations, RCRA compliance, Clean Air Act"
        platforms = "ThomasNet/GlobalSpec (50%): Recent buyer requirements with detailed technical specifications"
        currency_examples = "$100-500K, €80-400K"
    else:  # UAE
        search_domains = ["linkedin.com", "exportersuae.com", "dubaichamber.com", "chemicalsuae.com", "gulfindustryonline.com"]
        compliance_refs = "UAE Environmental regulations, ADNOC standards"
        platforms = "UAE B2B platforms (50%): Recent buyer requirements with detailed technical specifications"
        currency_examples = "AED 400K-2M, $100-500K"
    
    default_payload["search_domain_filter"] = search_domains
    
    user_content = f"""Find {num_leads} verified, high-conversion B2B prospects in {geography} actively seeking {selected_service.lower()} services right now.

**REAL-TIME RESEARCH REQUIREMENTS:**
1. Identify current major B2B platforms and professional networks active in {geography} for pharmaceutical/chemical outsourcing
2. Research active regulatory frameworks and compliance requirements in {geography} relevant to {selected_service.lower()}
3. Determine typical project budgets and currency preferences for {selected_service.lower()} services in {geography}
4. Find current market conditions and outsourcing trends in {geography}

**Target Company Profile:**
- Geography: {geography}
- Revenue Range: {revenue_range}
- Industry Focus: Pharmaceuticals, biotechnology, specialty chemicals, contract research organizations
- Service Need: {selected_service} - {SERVICES_CONFIG[selected_service]['description']}

**Dynamic Research Strategy:**
Research the most active and current platforms in {geography} for:
- B2B chemical/pharmaceutical outsourcing platforms (40%): Look for recent service RFQs and outsourcing announcements
- Professional networks and LinkedIn (35%): Current R&D posts, procurement announcements, project hiring trends
- Industry publications and trade news (25%): Recent partnership announcements, outsourcing market analysis

**Adaptive Keywords (Research Current Terminology):**
- Primary: "{selected_service.lower()} service provider {geography}", "{selected_service.lower()} contract manufacturing", "{selected_service.lower()} outsourcing partner"
- Pain-based: Research current challenges companies face with "{SERVICES_CONFIG[selected_service]['pain_points']}" in {geography}
- Technical: "cGMP {selected_service.lower()}", "pharmaceutical grade {selected_service.lower()}", "commercial scale {selected_service.lower()}"
- Geography-specific: Research local terminology and requirements for {selected_service.lower()} in {geography}

**Real-Time Qualification Requirements:**
✓ Verified pharmaceutical/chemical company with genuine {selected_service.lower()} needs
✓ Current R&D or procurement decision-maker with active outsourcing authority
✓ Recent (≤90 days) technical requirements and project specifications posted
✓ Current budget indicators, funding announcements, or development capital mentioned
✓ Active project timeline within 12 months with verified urgency signals
✓ Company revenue/funding currently in range: {revenue_range}

**Live Market Intelligence:**
- Research current companies in {geography} actively seeking: {SERVICES_CONFIG[selected_service]['pain_points']}
- Identify recent announcements of companies needing: {SERVICES_CONFIG[selected_service]['value_proposition']}
- Find real-time regulatory changes in {geography} affecting {selected_service.lower()} outsourcing
- Discover current competitive landscape and service provider gaps in {geography}

**Quality Standards:**
- All leads must have activity evidence from last 60 days
- Verify company legitimacy through current business registration status
- Confirm contact authority through recent professional activity
- Cross-reference all information across multiple current sources
- Prioritize companies with immediate, verified {selected_service.lower()} outsourcing needs

**Deliverable:**
{num_leads} prospects ranked by immediate project readiness (1-10), with real-time business intelligence, current contact verification, and specific next-step recommendations for immediate business development execution. Include source verification and data recency timestamps."""
    
    default_payload["messages"][1]["content"] = user_content
    edited_payload = default_payload

    # Generate leads button and show results below
    if "result_text" not in st.session_state:
        st.session_state["result_text"] = ""
    if "result_df" not in st.session_state:
        st.session_state["result_df"] = None
    if st.button("🔍 Generate Leads", type="primary"):
        # Professional step-by-step loader
        with st.spinner("Preparing search filters..."):
            # Simulate step 1
            import time
            time.sleep(0.7)
        with st.spinner("Querying Perplexity AI for real-time leads..."):
            try:
                result_chunks = list(stream_perplexity_response(edited_payload))
                raw_response = "".join(str(chunk) for chunk in result_chunks)
            except Exception as e:
                st.session_state["result_df"] = None
                st.session_state["result_text"] = f"❌ Error: {str(e)}"
                return
        with st.spinner("Parsing and formatting results..."):
            time.sleep(0.5)
            try:
                response_json = json.loads(raw_response)
                df = simple_extract_table(response_json)
                if df is not None:
                    st.session_state["result_df"] = df
                    table_text = df.to_string(index=False)
                else:
                    st.session_state["result_df"] = None
                    table_text = response_json["choices"][0]["message"]["content"]
            except Exception:
                st.session_state["result_df"] = None
                table_text = raw_response
            st.session_state["result_text"] = table_text
    # Show the result as a table if available, else fallback to text area
    if st.session_state.get("result_df") is not None:
        st.subheader("📊 Lead Results")
        
        # Add download button
        @st.cache_data
        def convert_df_to_excel(df):
            import io
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Leads')
            return output.getvalue()
        
        excel_data = convert_df_to_excel(st.session_state["result_df"])
        st.download_button(
            label="📥 Download Results as Excel",
            data=excel_data,
            file_name=f"leads_{selected_service.replace(' ', '_')}_{geography}_{num_leads}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="secondary"
        )
        
        # Display the dataframe with selection
        selected_indices = st.dataframe(
            st.session_state["result_df"], 
            on_select="rerun",
            selection_mode="single-row"
        )
        
        # Email generation section
        if selected_indices and len(selected_indices.selection.rows) > 0:
            selected_row_index = selected_indices.selection.rows[0]
            selected_contact = st.session_state["result_df"].iloc[selected_row_index].to_dict()
            
            st.subheader("🎯 Generate Content")
            
            # Brief contact card
            with st.container():
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.write(f"**{selected_contact.get('Contact Person & Title', 'N/A')}**")
                    st.write(f"*{selected_contact.get('Company Name', 'N/A')} • {selected_contact.get('Industry Vertical', 'N/A')}*")
                with col2:
                    st.write(f"📍 {selected_contact.get('Location (State)', 'N/A')}")
                    st.write(f"⭐ Score: {selected_contact.get('Qualification Score', 'N/A')}")
            
            st.divider()
            
            # Content type dropdown
            content_type = st.selectbox(
                "Choose content type to generate:",
                ["Generate Contact Profile", "Generate Personalized Email", "Sales Company Profile"],
                index=0
            )
            
            if st.button(f"🚀 Generate {content_type}", type="secondary"):
                with st.spinner(f"Generating {content_type.lower()}..."):
                    content = generate_content(
                        selected_contact, 
                        sender_company, 
                        sender_name, 
                        value_proposition, 
                        pain_point,
                        cta,
                        content_type,
                        selected_service,
                        geography  # Pass geography parameter
                    )
                    
                    # Show content in expandable section
                    if content_type == "Generate Contact Profile":
                        st.success("✅ LinkedIn|Google Profile Research Complete!")
                        with st.expander("👤 Contact Insights", expanded=True):
                            st.markdown(content)
                    elif content_type == "Generate Personalized Email":
                        st.success("✅ Personalized Email Generated!")
                        with st.expander("� Email Content", expanded=True):
                            st.markdown(content)
                            st.divider()
                            st.text_area("Copy Email", value=content, height=200, key="email_copy")
                    else:
                        st.success("✅ Company Profile Generated!")
                        with st.expander("🏢 Sales Intelligence", expanded=True):
                            st.markdown(content)
        else:
            st.info("👆 Select a row from the table above to generate content")
    else:
        st.text_area("Results", value=st.session_state["result_text"], height=400)
    
    # Footer
    st.divider()
    st.markdown(
        """
        <div style='text-align: center; color: #666;'>
            <small>Lead Gen | Powered by Perplexity AI | Created BY NIKHIL</small>
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()