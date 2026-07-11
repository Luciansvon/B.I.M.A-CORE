from pathlib import Path
from crewai import Agent
from config import admin_llm
from tools.image_search_tool import ImageSearchTool
from teams.t4_admin.excel_tool import ExcelGeneratorTool
from teams.t4_admin.word_tool import WordGeneratorTool
from teams.t4_admin.pdf_tool import PDFGeneratorTool
from teams.t4_admin.data_analysis_tool import DataAnalysisTool

_BACKSTORY_PATH = Path(__file__).parent / "prompt_templates" / "backstory.md"
_backstory = _BACKSTORY_PATH.read_text(encoding="utf-8")

admin_agent = Agent(
    role='Multi-Style Document Crafter',
    goal='Membuat dokumen Excel/Word/PDF dengan gaya tulisan dan layout yang menyesuaikan permintaan Bima — bukan hanya laporan formal.',
    backstory=_backstory,
    llm=admin_llm,
    tools=[ExcelGeneratorTool(), WordGeneratorTool(), PDFGeneratorTool(), DataAnalysisTool(), ImageSearchTool()],
    allow_delegation=True,
    verbose=True,
)
