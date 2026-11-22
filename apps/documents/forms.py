from django import forms
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from django.core.exceptions import ValidationError
from .services import validate_image_file
from .models import ProjectImage, ProjectDocument


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

    def __init__(self, attrs=None):
        input_attrs = {
            "accept": "image/*",
            "class": "form-control",
            "data-compress-images": "true",
        }
        if attrs:
            input_attrs.update(attrs)
        super().__init__(attrs=input_attrs)


class MultipleFileField(forms.FileField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        if not data:
            return []
        files = data if isinstance(data, (list, tuple)) else [data]
        return [super(MultipleFileField, self).clean(file, initial) for file in files]


class ProjectImageForm(forms.Form):
    images = MultipleFileField(label="Rasmlar")
    description = forms.CharField(max_length=255, required=False, label="Tavsif")

    def clean_images(self):
        images = self.cleaned_data["images"]
        if not images:
            raise ValidationError("Kamida bitta rasm tanlang.")
        if len(images) > 20:
            raise ValidationError("Bir martada ko'pi bilan 20 ta rasm tanlang.")
        if sum(image.size for image in images) > 100 * 1024 * 1024:
            raise ValidationError("Tanlangan rasmlarning umumiy hajmi 100 MB dan oshmasin.")
        for image in images:
            validate_image_file(image)
        return images


class ProjectImageEditForm(forms.ModelForm):
    class Meta:
        model = ProjectImage
        fields = ("description",)
        labels = {"description": "Izoh (ixtiyoriy)"}


class ProjectDocumentForm(forms.ModelForm):
    class Meta:
        model = ProjectDocument
        fields = ("title", "file", "description", "is_public")

    def clean_file(self):
        uploaded_file = self.cleaned_data["file"]
        if uploaded_file.size > 20 * 1024 * 1024:
            raise ValidationError("Fayl hajmi 20 MB dan oshmasligi kerak.")

        extension = Path(uploaded_file.name).suffix.lower()
        if extension not in {".pdf", ".doc", ".docx", ".mp4", ".webm"}:
            raise ValidationError("PDF, DOC, DOCX, MP4 yoki WebM faylini tanlang.")

        header = uploaded_file.read(8)
        uploaded_file.seek(0)
        if extension == ".pdf" and not header.startswith(b"%PDF-"):
            raise ValidationError("PDF fayl formati noto'g'ri.")
        if extension == ".doc" and not header.startswith(bytes.fromhex("D0CF11E0A1B11AE1")):
            raise ValidationError("DOC fayl formati noto'g'ri.")
        if extension == ".mp4" and header[4:8] != b"ftyp":
            raise ValidationError("MP4 fayl formati noto'g'ri.")
        if extension == ".webm" and not header.startswith(bytes.fromhex("1A45DFA3")):
            raise ValidationError("WebM fayl formati noto'g'ri.")
        if extension == ".docx":
            try:
                with ZipFile(uploaded_file) as archive:
                    names = set(archive.namelist())
                if "word/document.xml" not in names or "[Content_Types].xml" not in names:
                    raise ValidationError("DOCX fayl formati noto'g'ri.")
            except BadZipFile as exc:
                raise ValidationError("DOCX fayl formati noto'g'ri.") from exc
            finally:
                uploaded_file.seek(0)
        return uploaded_file
