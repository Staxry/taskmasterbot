"""
Statistics and Excel report generation service
"""
import io
from datetime import datetime, timedelta
from typing import Dict, Any
import matplotlib
matplotlib.use('Agg')  # Non-GUI backend
import matplotlib.pyplot as plt
from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.chart import BarChart, PieChart, Reference
from openpyxl.styles import Font, Alignment, PatternFill

from app.database import get_db_connection
from app.logging_config import get_logger

logger = get_logger(__name__)


def get_dashboard_statistics(user_role: str = 'admin') -> Dict[str, Any]:
    """
    Получить статистику для дашборда
    
    Args:
        user_role: Роль пользователя ('admin' или 'employee')
    
    Returns:
        Dict с метриками статистики
    """
    logger.info(f"📊 Generating dashboard statistics for role: {user_role}")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        stats = {}
        
        # Общее количество задач
        cur.execute("SELECT COUNT(*) as count FROM tasks")
        result = cur.fetchone()
        stats['total_tasks'] = result['count'] if result else 0
        
        # Задачи по статусам
        cur.execute("""
            SELECT status, COUNT(*) 
            FROM tasks 
            GROUP BY status
        """)
        status_counts = dict(cur.fetchall())
        stats['by_status'] = {
            'pending': status_counts.get('pending', 0),
            'in_progress': status_counts.get('in_progress', 0),
            'partially_completed': status_counts.get('partially_completed', 0),
            'completed': status_counts.get('completed', 0),
            'rejected': status_counts.get('rejected', 0)
        }
        
        # Активные задачи (не завершённые)
        stats['active_tasks'] = (
            stats['by_status']['pending'] + 
            stats['by_status']['in_progress'] + 
            stats['by_status']['partially_completed']
        )
        
        # Задачи по приоритетам
        cur.execute("""
            SELECT priority, COUNT(*) 
            FROM tasks 
            WHERE status NOT IN ('completed', 'rejected')
            GROUP BY priority
        """)
        stats['by_priority'] = dict(cur.fetchall())
        
        # Просроченные задачи
        cur.execute("""
            SELECT COUNT(*) as count 
            FROM tasks 
            WHERE due_date < datetime('now') 
            AND status NOT IN ('completed', 'rejected')
        """)
        result = cur.fetchone()
        stats['overdue_tasks'] = result['count'] if result else 0
        
        # Задачи за сегодня (созданные)
        cur.execute("""
            SELECT COUNT(*) as count 
            FROM tasks 
            WHERE DATE(created_at) = DATE('now')
        """)
        result = cur.fetchone()
        stats['today_created'] = result['count'] if result else 0
        
        # Завершённые за последние 7 дней
        cur.execute("""
            SELECT COUNT(*) as count 
            FROM tasks 
            WHERE status = 'completed'
            AND updated_at >= datetime('now', '-7 days')
        """)
        result = cur.fetchone()
        stats['completed_last_week'] = result['count'] if result else 0
        
        # Топ исполнителей
        cur.execute("""
            SELECT u.username, COUNT(t.id) as task_count
            FROM tasks t
            JOIN users u ON t.assigned_to_id = u.id
            WHERE t.status = 'completed'
            GROUP BY u.username
            ORDER BY task_count DESC
            LIMIT 5
        """)
        stats['top_performers'] = cur.fetchall()
        
        logger.info(f"✅ Dashboard statistics generated: {stats['total_tasks']} total tasks")
        return stats
        
    except Exception as e:
        logger.error(f"❌ Error generating dashboard statistics: {e}", exc_info=True)
        return {}
    finally:
        cur.close()
        conn.close()


def generate_excel_report(report_type: str = 'full') -> io.BytesIO:
    """
    Генерация Excel отчёта с графиками
    
    Args:
        report_type: Тип отчёта ('full', 'status', 'priority', 'users')
    
    Returns:
        BytesIO объект с Excel файлом
    """
    logger.info(f"📊 Generating Excel report: {report_type}")
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Статистика задач"
    
    # Заголовок
    ws['A1'] = "Отчёт по задачам"
    ws['A1'].font = Font(size=16, bold=True)
    ws['A2'] = f"Дата создания: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    ws['A2'].font = Font(size=10, italic=True)
    
    stats = get_dashboard_statistics()
    
    if not stats:
        logger.warning("⚠️ No statistics data available")
        ws['A4'] = "Нет данных для отчёта"
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return output
    
    # Общая статистика
    ws['A4'] = "Общая статистика"
    ws['A4'].font = Font(size=14, bold=True)
    ws['A4'].fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    ws['A4'].font = Font(size=14, bold=True, color="FFFFFF")
    
    row = 5
    ws[f'A{row}'] = "Всего задач:"
    ws[f'B{row}'] = stats['total_tasks']
    ws[f'B{row}'].font = Font(bold=True)
    
    row += 1
    ws[f'A{row}'] = "Активных задач:"
    ws[f'B{row}'] = stats['active_tasks']
    
    row += 1
    ws[f'A{row}'] = "Завершено:"
    ws[f'B{row}'] = stats['by_status']['completed']
    
    row += 1
    ws[f'A{row}'] = "Просрочено:"
    ws[f'B{row}'] = stats['overdue_tasks']
    ws[f'B{row}'].font = Font(color="FF0000", bold=True)
    
    # Статистика по статусам
    row += 2
    ws[f'A{row}'] = "Задачи по статусам"
    ws[f'A{row}'].font = Font(size=12, bold=True)
    ws[f'A{row}'].fill = PatternFill(start_color="70AD47", end_color="70AD47", fill_type="solid")
    ws[f'A{row}'].font = Font(size=12, bold=True, color="FFFFFF")
    
    row += 1
    status_labels = {
        'pending': 'Ожидает',
        'in_progress': 'В работе',
        'partially_completed': 'Частично завершена',
        'completed': 'Завершена',
        'rejected': 'Отклонена'
    }
    
    for status_key, label in status_labels.items():
        ws[f'A{row}'] = label
        ws[f'B{row}'] = stats['by_status'][status_key]
        row += 1
    
    # Топ исполнителей
    if stats.get('top_performers'):
        row += 1
        ws[f'A{row}'] = "Топ исполнителей"
        ws[f'A{row}'].font = Font(size=12, bold=True)
        ws[f'A{row}'].fill = PatternFill(start_color="FFC000", end_color="FFC000", fill_type="solid")
        ws[f'A{row}'].font = Font(size=12, bold=True, color="000000")
        
        row += 1
        ws[f'A{row}'] = "Исполнитель"
        ws[f'B{row}'] = "Завершено задач"
        ws[f'A{row}'].font = Font(bold=True)
        ws[f'B{row}'].font = Font(bold=True)
        
        row += 1
        for username, count in stats['top_performers']:
            ws[f'A{row}'] = username
            ws[f'B{row}'] = count
            row += 1
    
    # Автоматическая ширина столбцов
    ws.column_dimensions['A'].width = 30
    ws.column_dimensions['B'].width = 15
    
    # Создание графиков с matplotlib
    try:
        # График по статусам
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
        
        # Круговая диаграмма по статусам
        status_data = [v for v in stats['by_status'].values() if v > 0]
        status_labels_filtered = [status_labels[k] for k, v in stats['by_status'].items() if v > 0]
        colors = ['#FFA500', '#4169E1', '#FFD700', '#32CD32', '#FF6347']
        
        ax1.pie(status_data, labels=status_labels_filtered, autopct='%1.1f%%', colors=colors)
        ax1.set_title('Распределение задач по статусам', fontsize=14, fontweight='bold')
        
        # Столбчатая диаграмма приоритетов
        priority_labels = list(stats['by_priority'].keys())
        priority_values = list(stats['by_priority'].values())
        
        if priority_labels and priority_values:
            ax2.bar(priority_labels, priority_values, color=['#FF4444', '#FF8800', '#FFDD44', '#88DD44'])
            ax2.set_title('Задачи по приоритетам (активные)', fontsize=14, fontweight='bold')
            ax2.set_xlabel('Приоритет')
            ax2.set_ylabel('Количество задач')
        else:
            ax2.text(0.5, 0.5, 'Нет данных', ha='center', va='center', fontsize=14)
        
        plt.tight_layout()
        
        # Сохранение графика в BytesIO
        img_stream = io.BytesIO()
        plt.savefig(img_stream, format='png', dpi=100, bbox_inches='tight')
        img_stream.seek(0)
        plt.close(fig)
        
        # Вставка изображения в Excel (на новый лист)
        ws_charts = wb.create_sheet(title="Графики")
        img = XLImage(img_stream)
        ws_charts.add_image(img, 'A1')
        
        logger.info("✅ Excel charts generated successfully")
        
    except Exception as e:
        logger.error(f"❌ Error generating charts: {e}", exc_info=True)
    
    # Добавляем детальные таблицы по исполнителям
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Лист с выполненными задачами по исполнителям
        ws_completed = wb.create_sheet(title="Выполненные задачи")
        ws_completed['A1'] = "Выполненные задачи по исполнителям"
        ws_completed['A1'].font = Font(size=14, bold=True)
        ws_completed['A1'].fill = PatternFill(start_color="70AD47", end_color="70AD47", fill_type="solid")
        ws_completed['A1'].font = Font(size=14, bold=True, color="FFFFFF")
        
        # Заголовки таблицы
        ws_completed['A3'] = "Исполнитель"
        ws_completed['B3'] = "ID Задачи"
        ws_completed['C3'] = "Название"
        ws_completed['D3'] = "Приоритет"
        ws_completed['E3'] = "Дата завершения"
        
        for col in ['A3', 'B3', 'C3', 'D3', 'E3']:
            ws_completed[col].font = Font(bold=True)
            ws_completed[col].fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
        
        # Получаем выполненные задачи
        cur.execute("""
            SELECT 
                u.username,
                t.id,
                t.title,
                t.priority,
                t.updated_at
            FROM tasks t
            JOIN users u ON t.assigned_to_id = u.id
            WHERE t.status = 'completed'
            ORDER BY u.username, t.updated_at DESC
        """)
        
        completed_tasks = cur.fetchall()
        row_completed = 4
        for task in completed_tasks:
            username = task['username']
            task_id = task['id']
            title = task['title']
            priority = task['priority']
            updated_at = task['updated_at']
            
            ws_completed[f'A{row_completed}'] = username
            ws_completed[f'B{row_completed}'] = task_id
            ws_completed[f'C{row_completed}'] = title[:50]  # Ограничение длины
            ws_completed[f'D{row_completed}'] = priority
            ws_completed[f'E{row_completed}'] = updated_at if updated_at else ''
            row_completed += 1
        
        # Автоширина столбцов
        ws_completed.column_dimensions['A'].width = 20
        ws_completed.column_dimensions['B'].width = 10
        ws_completed.column_dimensions['C'].width = 40
        ws_completed.column_dimensions['D'].width = 12
        ws_completed.column_dimensions['E'].width = 18
        
        logger.info(f"✅ Added {len(completed_tasks)} completed tasks to report")
        
        # Лист с просроченными задачами
        ws_overdue = wb.create_sheet(title="Просроченные задачи")
        ws_overdue['A1'] = "Просроченные задачи по исполнителям"
        ws_overdue['A1'].font = Font(size=14, bold=True)
        ws_overdue['A1'].fill = PatternFill(start_color="FF0000", end_color="FF0000", fill_type="solid")
        ws_overdue['A1'].font = Font(size=14, bold=True, color="FFFFFF")
        
        # Заголовки таблицы
        ws_overdue['A3'] = "Исполнитель"
        ws_overdue['B3'] = "ID Задачи"
        ws_overdue['C3'] = "Название"
        ws_overdue['D3'] = "Приоритет"
        ws_overdue['E3'] = "Срок выполнения"
        ws_overdue['F3'] = "Статус"
        ws_overdue['G3'] = "Просрочено дней"
        
        for col in ['A3', 'B3', 'C3', 'D3', 'E3', 'F3', 'G3']:
            ws_overdue[col].font = Font(bold=True)
            ws_overdue[col].fill = PatternFill(start_color="FFE699", end_color="FFE699", fill_type="solid")
        
        # Получаем просроченные задачи
        cur.execute("""
            SELECT 
                u.username,
                t.id,
                t.title,
                t.priority,
                t.due_date,
                t.status,
                CAST((julianday('now') - julianday(t.due_date)) AS INTEGER) as days_overdue
            FROM tasks t
            JOIN users u ON t.assigned_to_id = u.id
            WHERE t.due_date < datetime('now') 
            AND t.status NOT IN ('completed', 'rejected')
            ORDER BY t.due_date ASC
        """)
        
        overdue_tasks = cur.fetchall()
        row_overdue = 4
        for task in overdue_tasks:
            username = task['username']
            task_id = task['id']
            title = task['title']
            priority = task['priority']
            due_date = task['due_date']
            status = task['status']
            days_overdue = task['days_overdue']
            
            ws_overdue[f'A{row_overdue}'] = username
            ws_overdue[f'B{row_overdue}'] = task_id
            ws_overdue[f'C{row_overdue}'] = title[:50]
            ws_overdue[f'D{row_overdue}'] = priority
            ws_overdue[f'E{row_overdue}'] = due_date if due_date else ''
            ws_overdue[f'F{row_overdue}'] = status
            ws_overdue[f'G{row_overdue}'] = int(days_overdue) if days_overdue else 0
            
            # Красный цвет для строк с высокой просрочкой
            if days_overdue and days_overdue > 7:
                for col in ['A', 'B', 'C', 'D', 'E', 'F', 'G']:
                    ws_overdue[f'{col}{row_overdue}'].fill = PatternFill(
                        start_color="FFB3B3", end_color="FFB3B3", fill_type="solid"
                    )
            
            row_overdue += 1
        
        # Автоширина столбцов
        ws_overdue.column_dimensions['A'].width = 20
        ws_overdue.column_dimensions['B'].width = 10
        ws_overdue.column_dimensions['C'].width = 40
        ws_overdue.column_dimensions['D'].width = 12
        ws_overdue.column_dimensions['E'].width = 15
        ws_overdue.column_dimensions['F'].width = 15
        ws_overdue.column_dimensions['G'].width = 15
        
        logger.info(f"✅ Added {len(overdue_tasks)} overdue tasks to report")
        
    except Exception as e:
        logger.error(f"❌ Error adding detailed task tables: {e}", exc_info=True)
    finally:
        cur.close()
        conn.close()
    
    # Сохранение в BytesIO
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    
    logger.info(f"✅ Excel report generated successfully: {output.getbuffer().nbytes} bytes")
    return output
