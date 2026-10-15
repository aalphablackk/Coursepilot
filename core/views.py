
from django.shortcuts import render

from .forms import GenerationForm


def generate(request):
    submitted = request.method == "POST"

    if submitted:
        form = GenerationForm(request.POST)
    else:
        form = GenerationForm()

    context = {
        "form": form,
        "submitted": submitted,
    }

    if submitted and form.is_valid():
        context["generation_data"] = form.cleaned_data

    return render(request, "generate.html", context)
