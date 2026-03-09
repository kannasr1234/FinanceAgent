from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
import os
from datetime import datetime
import logging
import asyncio

from services.stock_service import StockService
from services.news_service import NewsService
from services.summary_service import SummaryService
from services.options_signal_service import OptionsSignalService
from services.cache_service import CacheService
from utils.excel_handler import ExcelHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Stock Portfolio Dashboard")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

cache_service = CacheService()
stock_service = StockService(cache_service)
news_service = NewsService(cache_service)
excel_handler = ExcelHandler()

current_portfolio = []

async def analyze_ticker(ticker: str) -> dict:
    try:
        stock_data = await stock_service.fetch_stock_data(ticker)
        
        if not stock_data:
            return {"ticker": ticker, "error": "Failed to fetch data"}
        
        headlines = await news_service.fetch_news_headlines(ticker)
        stock_data["news"] = headlines
        
        summary = SummaryService.generate_summary(stock_data, headlines)
        stock_data["summary"] = summary
        
        signal, reason = OptionsSignalService.generate_signal(stock_data)
        stock_data["signal"] = signal.value
        stock_data["signal_label"] = OptionsSignalService.get_signal_label(signal)
        stock_data["signal_emoji"] = OptionsSignalService.get_signal_emoji(signal)
        stock_data["signal_reason"] = reason
        
        return stock_data
    except Exception as e:
        logger.error(f"Error analyzing {ticker}: {e}")
        return {"ticker": ticker, "error": "Analysis failed"}

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    global current_portfolio
    
    if not current_portfolio:
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "portfolio": [],
            "last_updated": None,
            "disclaimer": "This is NOT financial advice. Use this dashboard for informational purposes only."
        })
    
    try:
        tasks = [analyze_ticker(ticker) for ticker in current_portfolio]
        portfolio_data = await asyncio.gather(*tasks)
        
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "portfolio": portfolio_data,
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "disclaimer": "This is NOT financial advice. Use this dashboard for informational purposes only."
        })
    except Exception as e:
        logger.error(f"Error fetching portfolio data: {e}")
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "portfolio": [],
            "error": "Failed to fetch portfolio data. Please refresh.",
            "last_updated": None,
            "disclaimer": "This is NOT financial advice. Use this dashboard for informational purposes only."
        })

@app.post("/upload")
async def upload_excel(file: UploadFile = File(...)):
    global current_portfolio
    
    try:
        if not file.filename.endswith(('.xls', '.xlsx')):
            raise HTTPException(status_code=400, detail="File must be .xls or .xlsx")
        
        temp_path = f"/tmp/{file.filename}"
        contents = await file.read()
        with open(temp_path, "wb") as f:
            f.write(contents)
        
        tickers = excel_handler.parse_excel(temp_path)
        
        if not tickers:
            raise HTTPException(status_code=400, detail="No tickers found in Excel file")
        
        current_portfolio = tickers
        logger.info(f"Loaded {len(tickers)} tickers: {tickers}")
        
        os.remove(temp_path)
        
        return {
            "status": "success",
            "tickers_loaded": len(tickers),
            "tickers": tickers
        }
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

@app.get("/refresh")
async def refresh_data():
    global current_portfolio
    
    if not current_portfolio:
        return {"status": "error", "message": "No portfolio loaded"}
    
    try:
        tasks = [analyze_ticker(ticker) for ticker in current_portfolio]
        portfolio_data = await asyncio.gather(*tasks)
        
        return {
            "status": "success",
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "stocks_updated": len(portfolio_data)
        }
    except Exception as e:
        logger.error(f"Error refreshing data: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/portfolio")
async def get_portfolio():
    global current_portfolio
    
    if not current_portfolio:
        return {"portfolio": [], "last_updated": None}
    
    try:
        tasks = [analyze_ticker(ticker) for ticker in current_portfolio]
        portfolio_data = await asyncio.gather(*tasks)
        
        return {
            "portfolio": portfolio_data,
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        logger.error(f"Error fetching portfolio: {e}")
        return {"portfolio": [], "error": str(e)}

@app.on_event("startup")
async def startup_event():
    cache_service.cleanup_old_cache()
    logger.info("Application started")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
