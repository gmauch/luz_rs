import os
import pathlib
import re
from decimal import Decimal
from os import listdir
from os.path import isfile, join, splitext

import click
import pytesseract
from PIL import Image
from pdf2image import convert_from_path
from pdfminer.high_level import extract_text


# def scan_image_pdf(filePath):
#     doc = convert_from_path(filePath)
#
#     for page_number, page_data in enumerate(doc):
#         txt = pytesseract.image_to_string(Image.fromarray(page_data)).encode("utf-8")
#         print("Page # {} - {}".format(str(page_number), txt))


class FilesProcessor:
    def __init__(self, input_folder, output_folder, debug=True):
        self.input_folder = input_folder
        self.output_folder = output_folder
        self.outfile = f'{self.output_folder}/out_text.txt'
        self.debug = debug

    def log(self, message):
        if self.debug:
            print(message)

    def process_folder(self, as_image):
        saved_files = []
        for filename in list(pathlib.Path(self.input_folder).glob('**/*.pdf')):
            saved_file = os.path.join(self.output_folder, self.create_output_filename(filename))
            if os.path.exists(saved_file):
                self.log(f'  Skipping {filename}! Dest file {saved_file} already exists.')
                saved_files.append(saved_file)
                continue

            self.log(f'Processing {filename}')
            if as_image:
                text = self.scan_image_pdf(filename)
            else:
                text = self.scan_pdf(filename)

            self.save_text_to_file(text, saved_file)
            self.log(f'  Saving {filename} text to {saved_file}')
            saved_files.append(saved_file)

        Fatura(self.output_folder, self.debug).process_files(saved_files)

    def create_output_filename(self, filename):
        name_ext = os.path.basename(filename)
        dot_position = name_ext.index('.')
        return f'{name_ext[:dot_position]}.txt'

    def save_text_to_file(self, text, output_file):
        text = text.replace('-\n', '')

        # Finally, write the processed text to the file.
        f = open(output_file, "a")
        f.write(text)

    def scan_pdf(self, pdf_path):
        text = extract_text(pdf_path)
        return text

    def scan_image_pdf(self, pdf_path):
        # Store all the pages of the PDF in a variable
        pages = convert_from_path(pdf_path)

        # Counter to store images of each page of PDF to image
        image_counter = 1

        # Iterate through all the pages stored above
        for page in pages:
            # Declaring filename for each page of PDF as JPG
            # For each page, filename will be:
            # PDF page 1 -> page_1.jpg
            # PDF page 2 -> page_2.jpg
            # PDF page 3 -> page_3.jpg
            # ....
            # PDF page n -> page_n.jpg
            filename = f'{self.output_folder}/page_{str(image_counter)}.jpg'

            # Save the image of the page in system
            page.save(filename, 'JPEG')

            # Increment the counter to update filename
            image_counter = image_counter + 1

            ''' 
            Part #2 - Recognizing text from the images using OCR 
            '''
            # Variable to get count of total number of pages
            filelimit = image_counter - 1

            # Open the file in append mode so that
            # All contents of all images are added to the same file
            f = open(self.outfile, "a")

            # Iterate from 1 to total number of pages
            result = ''
            for i in range(1, filelimit + 1):
                # Set filename to recognize text from
                # Again, these files will be:
                # page_1.jpg
                # page_2.jpg
                # ....
                # page_n.jpg
                filename = f'{self.output_folder}/page_{str(i)}.jpg'

                # Recognize the text as string in image using pytesserct
                text = str(((pytesseract.image_to_string(Image.open(filename), lang='por'))))

                # The recognized text is stored in variable text
                # Any string processing may be applied on text
                # Here, basic formatting has been done:
                # In many PDFs, at line ending, if a word can't
                # be written fully, a 'hyphen' is added.
                # The rest of the word is written in the next line
                # Eg: This is a sample text this word here GeeksF-
                # orGeeks is half on first line, remaining on next.
                # To remove this, we replace every '-\n' to ''.
                text = text.replace('-\n', '')

                # Finally, write the processed text to the file.
                f.write(text)
                result += text

                # Close the file after writing all the text.
            f.close()

            return result


class ICMS:
    def __init__(self, ano_mes, icms):
        self.ano_mes = ano_mes
        self.icms_orig = round(Decimal(icms[0]), 2)
        self.icms_reduz = round(Decimal(icms[1]), 2)
        self.icms_diff = self.icms_orig - self.icms_reduz


class Fatura:
    # Aqui teria que somar todos os valores:
    # TRANSMISSÃO
    # DISTRIBUIÇÃO
    # ENCARGOS SETORIAIS
    # TRIBUTOS
    # PERDAS
    # OUTROS
    # Calcular o ICMS (30%).
    # Depois recalcular o ICMS, mas excluindo TRANSMISSÃO, DISTRIBUIÇÃO e ENCARGOS SETORIAIS.

    FATURA_BEGIN_MARKER = 'Composição da Fatura'
    FATURA_END_MARKER = 'kWh'
    ENERGIA = 'energia'
    TRANSMISSAO = 'transmissao'
    DISTRIBUICAO = 'distribuicao'
    ENCARGOS = 'setoriais'
    TRIBUTOS = 'tributos'
    PERDAS = 'perdas'
    OUTROS = 'outros'
    ICMS = 0.30

    SUMMARY_INFO = 'GERAL'
    SUMMARY_ERROR = 'ERRO'
    SUMMARY_SUCCESS = 'SUCESSO'

    def __init__(self, output_folder, debug=True):
        self.values_read = {}
        self.output_file = f'{output_folder}/icms.csv'
        self.debug = debug
        self.summary = {self.SUMMARY_INFO: 'RESUMO GERAL\n',
                        self.SUMMARY_SUCCESS: 'SUCESSO\n',
                        self.SUMMARY_ERROR: 'ERROS DE PROCESSAMENTO\n'}

    @property
    def energia(self):
        return self.values_read.get(self.ENERGIA, 0)

    @property
    def transmissao(self):
        return self.values_read.get(self.TRANSMISSAO, 0)

    @property
    def distribuicao(self):
        return self.values_read.get(self.DISTRIBUICAO, 0)

    @property
    def encargos(self):
        return self.values_read.get(self.ENCARGOS, 0)

    @property
    def tributos(self):
        return self.values_read.get(self.TRIBUTOS, 0)

    @property
    def perdas(self):
        return self.values_read.get(self.PERDAS, 0)

    @property
    def outros(self):
        return self.values_read.get(self.OUTROS, 0)

    def log(self, message):
        if self.debug:
            print(message)

    def add_general_info_to_summary(self, message):
        self.add_to_summary(self.SUMMARY_INFO, message)

    def add_error_to_summary(self, message):
        self.add_to_summary(self.SUMMARY_ERROR, message)

    def add_success_to_summary(self, message):
        self.add_to_summary(self.SUMMARY_SUCCESS, message)

    def add_to_summary(self, append_to, message):
        self.summary[append_to] += f'    {message}\n'

    def log_summary(self):
        self.log(self.summary[self.SUMMARY_INFO])
        self.log(self.summary[self.SUMMARY_SUCCESS])
        self.log(self.summary[self.SUMMARY_ERROR])

    def _write_icms_header(self):
        f = open(self.output_file, "w")
        f.write('DATA;ICMS ORIGINAL;ICMS REDUZIDO;DIFERENÇA;\n')
        f.close()

    def add_icms_diff(self, icms):
        f = open(self.output_file, "a")
        if not os.path.isfile(self.output_file):
            self._write_icms_header()
        f.write(f'{icms.ano_mes};{round(icms.icms_orig, 2)};{round(icms.icms_reduz, 2)};{round(icms.icms_diff, 2)};\n')

    def process_files(self, files_list):
        self._write_icms_header()
        self.log('Writing ICMS header')
        self.add_general_info_to_summary(f'{len(files_list)} arquivos a processar')
        for conta in files_list:
            self.log(f'Calculating ICMS for {conta}')
            computed_icms = self.readlines(conta)
            if computed_icms:
                self.log(f'  ICMS original {computed_icms.icms_orig}')
                self.log(f'  ICMS reduzido {computed_icms.icms_reduz}')
                self.log(f'  ICMS diferença {computed_icms.icms_diff}')
                self.add_icms_diff(computed_icms)
                self.log('  Written ICMS values')

        self.log_summary()

    def readlines(self, infile):
        processing_fatura = False
        try:
            with open(infile) as f:
                lines = [line.rstrip() for line in f]
                for line in lines:
                    if re.search(self.FATURA_BEGIN_MARKER, line, re.IGNORECASE):
                        processing_fatura = True
                    if processing_fatura:
                        self.read_fatura_line(line)
                    if processing_fatura and re.search(self.FATURA_END_MARKER, line, re.IGNORECASE):
                        break

                icms = self.read_icms_values()
                self.add_success_to_summary(infile)
                return ICMS(os.path.basename(infile), icms)
        except:
            self.log(f'Error parsing line {line}')
            self.add_error_to_summary(infile)
            return None

    def read_fatura_line(self, line):
        if re.findall(self.ENERGIA, line, re.IGNORECASE):
            self.values_read[self.ENERGIA] = Decimal(re.findall('\d+\,\d+', line, re.IGNORECASE)[0].replace(',', '.'))
            self.log(f'  ENERGIA={self.values_read[self.ENERGIA]}')
        elif re.findall(self.TRANSMISSAO, line, re.IGNORECASE):
            self.values_read[self.TRANSMISSAO] = Decimal(re.findall('\d+\,\d+', line, re.IGNORECASE)[0].replace(',', '.'))
            self.log(f'  TRANSMISSAO={self.values_read[self.TRANSMISSAO]}')
        elif re.findall(self.DISTRIBUICAO, line, re.IGNORECASE):
            self.values_read[self.DISTRIBUICAO] = Decimal(re.findall('\d+\,\d+', line, re.IGNORECASE)[0].replace(',', '.'))
            self.log(f'  DISTRIBUICAO={self.values_read[self.DISTRIBUICAO]}')
        elif re.findall(self.ENCARGOS, line, re.IGNORECASE):
            self.values_read[self.ENCARGOS] = Decimal(re.findall('\d+\,\d+', line, re.IGNORECASE)[0].replace(',', '.'))
            self.log(f'  ENCARGOS={self.values_read[self.ENCARGOS]}')
        elif re.findall(self.TRIBUTOS, line, re.IGNORECASE):
            self.values_read[self.TRIBUTOS] = Decimal(re.findall('\d+\,\d+', line, re.IGNORECASE)[0].replace(',', '.'))
            self.log(f'  TRIBUTOS={self.values_read[self.TRIBUTOS]}')
        elif re.findall(self.PERDAS, line, re.IGNORECASE):
            self.values_read[self.PERDAS] = Decimal(re.findall('\d+\,\d+', line, re.IGNORECASE)[0].replace(',', '.'))
            self.log(f'  PERDAS={self.values_read[self.PERDAS]}')
        elif re.findall(self.OUTROS, line, re.IGNORECASE):
            self.values_read[self.OUTROS] = Decimal(re.findall('\d+\,\d+', line, re.IGNORECASE)[0].replace(',', '.'))
            self.log(f'  OUTROS={self.values_read[self.OUTROS]}')

    def read_icms_values(self):
        self._check_needed_values()
        total_value = round(float(self.energia + self.transmissao + self.distribuicao + self.encargos + self.tributos + self.perdas + self.outros) * self.ICMS, 2)
        reduced_value = float(self.energia + self.tributos + self.perdas + self.outros) * self.ICMS
        return total_value, reduced_value

    def _check_needed_values(self):
        if self.energia == 0 and self.transmissao == 0 and self.distribuicao == 0\
                and self.encargos == 0 and self.tributos == 0:
            raise Exception('Nao foi possivel ler todos os valores necessarios')


class ContasDeLuzProcessor:
    input_folder = './contas/'
    output_folder = './out/'
    valid_extensions = ['pdf']

    def save_pdf_as_images(self):
        pdfs = [f for f in listdir(self.input_folder) if isfile(join(self.input_folder, f) and splitext(f) in self.valid_extensions)]
        for pdf in pdfs:
            # Store all the pages of the PDF in a variable
            pages = convert_from_path(pdf)

            # Counter to store images of each page of PDF to image
            image_counter = 1

            for page in pages:
                filename = f'{self.output_folder}/page_{str(image_counter)} + .jpg'

                # Save the image of the page in system
                page.save(filename, 'JPEG')

                # Increment the counter to update filename
                image_counter = image_counter + 1


@click.argument('input_folder')
@click.argument('output_folder')
@click.option('--as_image', is_flag=True, default=False)
@click.option('--debug', is_flag=True, default=True)
@click.command()
def cli(input_folder, output_folder, as_image=False, debug=True):
    file_processor = FilesProcessor(output_folder, input_folder)
    file_processor.process_folder(as_image)


if __name__ == '__main__':
    cli()
