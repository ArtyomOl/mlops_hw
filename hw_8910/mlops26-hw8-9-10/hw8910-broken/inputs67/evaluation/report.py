"""Совместимая точка входа; постобработка не меняет протокол генерации и scorer.

Отчёт вынесен в scripts/report.py: его оформление не требует новой генерации.
Метрики и решение по-прежнему проверяются current_reports и quality_gate.
"""
from scripts.report import main


if __name__ == "__main__":
    main()
