"""Bounded pronunciation of standalone small integers; versions/decimals stay unchanged."""
import re
SMALL=('ноль','один','два','три','четыре','пять','шесть','семь','восемь','девять','десять','одиннадцать','двенадцать','тринадцать','четырнадцать','пятнадцать','шестнадцать','семнадцать','восемнадцать','девятнадцать')
TENS=('','','двадцать','тридцать','сорок','пятьдесят','шестьдесят','семьдесят','восемьдесят','девяносто')
def small_integer(value):
    if value<20:return SMALL[value]
    if value==100:return 'сто'
    return TENS[value//10]+(' '+SMALL[value%10] if value%10 else '')
def russian_numbers(text):
    return re.sub(r'(?<!\w)(?<!\d[.,])(?:100|[1-9]?\d)(?!\w|[.,]\d)',lambda match:small_integer(int(match[0])),text)
