import re
import logging
from pathlib import Path
from typing import Iterable, Text, List, Any, Tuple, Optional

from handsdown.loader import Loader, LoaderError
from handsdown.processors.smart import SmartDocstringProcessor
from handsdown.processors.base import BaseDocstringProcessor
from handsdown.utils import get_anchor_link, generate_toc_lines
from handsdown.module_record import ModuleRecord, ModuleObjectRecord, ModuleRecordList


class GeneratorError(Exception):
    pass


class Generator:
    """
    Main doc generator.

    Arguments:
        input_path -- Path to repo to generate docs.
        logger -- Logger instance.
        docstring_processor -- Docstring converter to Markdown.
        loader -- Loader for python modules.
        output_path -- Path to folder with auto-generated docs to output.
    """

    ignore_paths = ["build/**", "docs/**", "dist/**", "test/**", "tests/**"]

    def __init__(
        self,
        input_path: Path,
        source_paths: Iterable[Path],
        logger: Optional[logging.Logger] = None,
        docstring_processor: Optional[BaseDocstringProcessor] = None,
        loader: Optional[Loader] = None,
        output_path: Optional[Path] = None,
        raise_import_errors: bool = False,
    ) -> None:
        self._logger = logger or logging.Logger("handsdown")
        self._repo_path = input_path
        self._docs_path = (
            output_path if output_path is not None else (input_path / "docs")
        )

        if not self._docs_path.exists():
            self._logger.info(f"Creating folder {self._docs_path}")
            self._docs_path.mkdir()

        self._raise_import_errors = raise_import_errors
        self._loader = loader or Loader(self._repo_path)
        self._docstring_processor = docstring_processor or SmartDocstringProcessor()

        self._source_paths = sorted(source_paths)
        self._module_records = self._build_module_record_list()

        package_names = self._module_records.get_package_names()
        self._docstring_links_re = re.compile(f'`(?:{"|".join(package_names)})\\.\\S+`')
        self._signature_links_re = re.compile(
            f'[ \\[]((?:{"|".join(package_names)})\\.[^() :,]+)'
        )

    def _build_module_record_list(self):
        result = ModuleRecordList()
        for source_path in self._source_paths:
            try:
                module_record = self._loader.get_module_record(source_path)
            except LoaderError as e:
                if self._raise_import_errors:
                    raise

                self._logger.warning(
                    f"Skipping {source_path.relative_to(self._repo_path)} due to import error: {e}"
                )

            if module_record:
                result.add(module_record)

        return result

    def cleanup_old_docs(self) -> None:
        """
        Remove old docs generated for this module.

        Arguments:
            preserve_paths -- All doc files generated paths that should not be deleted.
        """
        preserve_file_names = self._module_records.get_output_file_names()
        for doc_path in self._docs_path.glob("*.md"):
            md_name = doc_path.name
            if md_name in preserve_file_names:
                continue

            file_content = doc_path.read_text()
            is_autogenerated = "Auto-generated documentation" in file_content
            if is_autogenerated:
                self._logger.info(f"Deleting orphaned doc file {md_name}")
                doc_path.unlink()

    def _generate_doc(self, module_record: ModuleRecord) -> None:
        """
        Generate one module doc at once. If `file_path` has nothing to document - return `None`.

        Arguments:
            file_path -- Path to source file.

        Returns:
            A path to generated MD file or None.
        """
        md_name = module_record.output_file_name
        target_file = self._docs_path / md_name
        relative_doc_path = target_file.relative_to(self._repo_path)
        relative_file_path = module_record.source_path.relative_to(self._repo_path)
        self._logger.info(
            f"Generating doc {relative_doc_path} for {relative_file_path}"
        )

        header_lines = self._generate_module_doc_header_lines(
            inspect_module=module_record.module, source_path=module_record.source_path
        )

        content_lines = self._generate_module_doc_lines(
            module_record_objects=module_record.objects,
            source_path=module_record.source_path,
        )

        toc_lines = generate_toc_lines("\n".join(header_lines + content_lines))
        md_lines = []
        md_lines.extend(header_lines[:2])
        md_lines.extend(toc_lines)
        md_lines.append("")
        md_lines.extend(header_lines[2:])
        md_lines.extend(content_lines)

        target_file.write_text("\n".join(md_lines))
        return target_file

    def generate(self) -> None:
        """
        Generate all module docs at once.
        """
        self._logger.debug(
            f"Generating docs for {self._repo_path.name} to {self._docs_path.relative_to(self._repo_path.parent)}"
        )

        for module_record in self._module_records:
            self._generate_doc(module_record)
            output_file_path = self._docs_path / module_record.output_file_name
            self.replace_links(output_file_path)

        self._logger.debug(f"Removing orphaned docs")
        self.cleanup_old_docs()

        index_md_path = Path(self._docs_path, "index.md")
        self._logger.info(f"Generating {index_md_path.relative_to(self._repo_path)}")
        index_md_path.write_text(self._generate_index_md_content())
        self.replace_links(index_md_path)

    @staticmethod
    def _get_title_from_import_string(import_string: Text, md_file_name: Text) -> Text:
        import_parts = import_string.split(".")
        first_import_part = import_parts[0]
        while md_file_name.startswith(first_import_part):
            import_parts = import_parts[1:]
            md_file_name = md_file_name[(len(first_import_part) + 1) :]
            if not import_parts:
                break
            first_import_part = import_parts[0]

        return ".".join(import_parts)

    def replace_links(self, file_path: Path) -> None:
        """
        Replace all import strings with Markdown links. Only import strings that present in this
        package are replaced, so not dead linsk should be generated.

        ```python
        my_md = Path('doc.md')
        my_md.write_text('I love `' + 'handsdown.indent_trimmer.IndentTrimmer.trim_lines` function!')
        handsdown.replace_links(my_md)

        my_md.read_text()
        # 'I love [IndentTrimmer.trim_lines](./handsdown_indent_trimmer.md#indenttrimmertrim_lines) function!'
        ```

        Arguments:
            file_path -- Path to MD document file.
        """
        content = file_path.read_text()
        file_changed = False
        for match in re.findall(self._docstring_links_re, content):
            module_name = match.replace("`", "")
            module_object_record = self._module_records.find_object(module_name)
            md_name = module_object_record.output_file_name
            if md_name == file_path.name:
                continue

            title = module_object_record.title
            anchor_link = get_anchor_link(title)
            link = f"[{title}](./{md_name}#{anchor_link})"
            content = content.replace(match, link)
            self._logger.debug(f'Adding link "{title}" to {file_path.name}')
            file_changed = True

        if file_changed:
            file_path.write_text(content)

    def _generate_module_doc_header_lines(
        self, inspect_module: Any, source_path: Path
    ) -> List[Text]:
        import_string = self._get_file_import_string(source_path)
        lines = []

        # Grab README.md content for __init__.py if it exists
        if source_path.name == "__init__.py":
            if (source_path.parent / "README.md").exists():
                for line in (source_path.parent / "README.md").read_text().split("\n"):
                    lines.append(line.rstrip())

            lines.append("")

        formatted_docstring = self._get_formatted_docstring(
            source_path=source_path, module_object=inspect_module
        )
        if formatted_docstring:
            docstring_lines = formatted_docstring.split("\n")
            for line in docstring_lines:
                lines.append(line.rstrip())

            lines.append("")

        if not lines or not lines[0].startswith("# "):
            page_title = self._get_title_from_path(
                source_path.relative_to(self._repo_path)
            )
            lines.insert(0, "")
            lines.insert(0, f"# {page_title}")

        lines.insert(
            1,
            f"> Auto-generated documentation for [{import_string}](../{source_path}) module.",
        )
        lines.insert(1, "")

        if lines[-1]:
            lines.append("")

        return lines

    def _generate_module_doc_lines(
        self, module_record_objects: List[ModuleObjectRecord], source_path: Path
    ) -> List[Text]:
        lines = []
        for module_record_object in module_record_objects:
            lines.append(
                f'{"#" * (module_record_object.level + 2)} {module_record_object.title}\n'
            )

            relative_path = source_path.relative_to(self._repo_path)
            lines.append(
                f"[🔍 find in source code](../{relative_path}#L{module_record_object.source_line_number})\n"
            )

            signature = self._loader.get_object_signature(module_record_object.object)

            if signature:
                lines.append(f"```python\n{signature}\n```")

            formatted_docstring = self._get_formatted_docstring(
                source_path=source_path, module_object=module_record_object.object
            )
            if formatted_docstring:
                lines.extend(formatted_docstring.split("\n"))
                lines.append("")

        return lines

    def _get_formatted_docstring(
        self, source_path: Path, module_object: Any
    ) -> Optional[Text]:
        """
        Get object docstring and convert it to a valid markdown using
        `handsdown.processors.base.BaseDocstringProcessor`.

        Arguments:
            source_path -- Path to object source file.
            module_object -- Object to inspect.

        Returns:
            A module docstring with valid markdown.
        """
        current_md_name = self._get_md_name(source_path)
        docstring = self._loader.get_object_docstring(module_object)
        if not docstring:
            return None

        sections = self._docstring_processor.build_sections(docstring)
        signature = self._loader.get_object_signature(module_object)
        if signature:
            added_module_object_records: List[ModuleObjectRecord] = []
            for match in re.findall(self._signature_links_re, signature):
                module_object_record = self._module_records.find_object(match)
                if (
                    not module_object_record
                    or module_object_record in added_module_object_records
                ):
                    continue

                md_name = module_object_record.output_file_name
                if md_name == current_md_name:
                    continue

                added_module_object_records.append(module_object_record)
                title = module_object_record.title
                anchor_link = get_anchor_link(title)
                sections["See also"].append(f"- [{title}](./{md_name}#{anchor_link})")
                self._logger.debug(
                    f'Adding link "{title}" to {current_md_name} "See also" section'
                )

        formatted_docstring = self._docstring_processor.render_sections(sections)
        return formatted_docstring.strip("\n")

    def _generate_index_md_content(self) -> Text:
        """
        Get new `index.md` file content. Copy content from `README.md` and add ToC.

        Arguments:
            source_paths -- List of source paths to include to `Modules` section.

        Returns:
            A string with new file content.
        """
        lines = []
        readme_path = Path(self._repo_path / "README.md")
        if readme_path.exists():
            lines.extend(readme_path.read_text().split("\n"))
        lines.append("\n## Modules\n")
        last_path_parts: Tuple[Text, ...] = tuple()
        for module_record in self._module_records:
            md_name = module_record.output_file_name
            relative_path = module_record.source_path.relative_to(self._repo_path)
            path_parts = relative_path.parts

            if path_parts[-1] == "__init__.py":
                path_parts = path_parts[:-1]

            for part_index, path_part in enumerate(path_parts):
                if (
                    len(last_path_parts) > part_index
                    and path_part == last_path_parts[part_index]
                ):
                    continue
                indent = "  " * part_index
                if part_index == len(path_parts) - 1:
                    title = self._get_title_from_md_content(
                        (self._docs_path / md_name).read_text()
                    )
                    if title:
                        title = title.split(": ")[-1]
                        lines.append(f"{indent}- [{title}](./{md_name})")
                else:
                    title = self._get_title_from_path(Path(path_part))
                    lines.append(f"{indent}- {title}")

            last_path_parts = path_parts

        toc_lines = generate_toc_lines("\n".join(lines))
        lines.insert(1, "\n".join(toc_lines))
        lines.insert(1, "")

        return "\n".join(lines)

    def _get_md_name(self, path: Path) -> Text:
        relative_path = path.relative_to(self._repo_path)
        name_parts = []
        for part in relative_path.parts:
            if part == "__init__.py":
                part = "index"
            stem = part.split(".")[0]
            name_parts.append(stem)

        if not name_parts:
            return "stub.md"

        return f"{'_'.join(name_parts)}.md"

    @staticmethod
    def _get_file_import_string(path: Path) -> Text:
        name_parts = []
        for part in path.parts:
            stem = part.split(".")[0]
            if stem == "__init__":
                continue
            name_parts.append(stem)

        return f"{'.'.join(name_parts)}"

    def _get_title_from_path(self, path: Path) -> Text:
        """
        Converts `pathlib.Path` to a human readable title.

        Arguments:
            path -- Relative path to file or folder

        Returns:
            Human readable title.
        """
        path_parts = path.parts
        name_parts = []
        for path_part in path_parts:
            if path_part == "__init__.py":
                continue
            name = path_part.split(".")[0]
            name = name.replace("__", "").replace("_", " ")
            name = name.capitalize()
            name_parts.append(name)

        if name_parts:
            return ": ".join(name_parts)

        return "Index"

    @staticmethod
    def _get_title_from_md_content(content: Text) -> Optional[Text]:
        lines = content.split("\n")[:10]
        for line in lines:
            if line.startswith("# "):
                return line.split(" ", 1)[-1].strip()

        return None
