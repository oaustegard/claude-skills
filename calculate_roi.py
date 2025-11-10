#!/usr/bin/env python3
"""
Calculate ROI for claude-skills repository based on industry benchmarks.
"""

import json
from dataclasses import dataclass
from typing import Dict

@dataclass
class ProductivityBenchmarks:
    """Industry productivity benchmarks from research."""

    # Lines of code per day (conservative estimate from research)
    # Source: US projects mean 26.4, median 17.6 LOC/day
    # Using conservative estimate for quality code with testing
    code_loc_per_day: float = 20.0

    # Technical documentation lines per day
    # Source: 2 pages/day for technical docs (research + editing)
    # Assuming ~50 lines per page of markdown
    doc_lines_per_day: float = 100.0

    # Architecture/planning documentation (slower, more thought required)
    # Using 60% of general doc speed for architectural planning
    architecture_lines_per_day: float = 60.0

    # Workflow/CI automation lines per day
    # Similar to code but less complexity
    workflow_lines_per_day: float = 25.0

    # Hours per working day
    hours_per_day: float = 8.0

    # Planning overhead (30% of total time per research)
    planning_overhead_factor: float = 0.30


class ROICalculator:
    """Calculate development time estimates for the repository."""

    def __init__(self, stats: Dict, benchmarks: ProductivityBenchmarks):
        self.stats = stats
        self.benchmarks = benchmarks

    def calculate_code_time(self) -> Dict:
        """Calculate time for code implementation."""
        total_lines = self.stats['code']['lines']
        days = total_lines / self.benchmarks.code_loc_per_day

        return {
            'lines': total_lines,
            'days': days,
            'hours': days * self.benchmarks.hours_per_day,
            'breakdown': {}
        }

    def calculate_markdown_time(self) -> Dict:
        """Calculate time for markdown documentation."""
        breakdown = self.stats['markdown']['breakdown']

        # Skill definitions are architectural/planning
        skill_lines = breakdown.get('skill_definitions', 0)
        skill_days = skill_lines / self.benchmarks.architecture_lines_per_day

        # Documentation is general technical writing
        doc_lines = breakdown.get('documentation', 0)
        doc_days = doc_lines / self.benchmarks.doc_lines_per_day

        # References are detailed technical docs
        ref_lines = breakdown.get('references', 0)
        ref_days = ref_lines / self.benchmarks.doc_lines_per_day

        # Other markdown
        other_lines = breakdown.get('other', 0)
        other_days = other_lines / self.benchmarks.doc_lines_per_day

        total_days = skill_days + doc_days + ref_days + other_days

        return {
            'lines': self.stats['markdown']['lines'],
            'days': total_days,
            'hours': total_days * self.benchmarks.hours_per_day,
            'breakdown': {
                'skill_definitions': {
                    'lines': skill_lines,
                    'days': skill_days,
                    'hours': skill_days * self.benchmarks.hours_per_day
                },
                'documentation': {
                    'lines': doc_lines,
                    'days': doc_days,
                    'hours': doc_days * self.benchmarks.hours_per_day
                },
                'references': {
                    'lines': ref_lines,
                    'days': ref_days,
                    'hours': ref_days * self.benchmarks.hours_per_day
                },
                'other': {
                    'lines': other_lines,
                    'days': other_days,
                    'hours': other_days * self.benchmarks.hours_per_day
                }
            }
        }

    def calculate_workflows_time(self) -> Dict:
        """Calculate time for workflow/CI files."""
        total_lines = self.stats['workflows']['lines']
        days = total_lines / self.benchmarks.workflow_lines_per_day if total_lines > 0 else 0

        return {
            'lines': total_lines,
            'days': days,
            'hours': days * self.benchmarks.hours_per_day
        }

    def calculate_total(self) -> Dict:
        """Calculate total development time with planning overhead."""
        code_time = self.calculate_code_time()
        markdown_time = self.calculate_markdown_time()
        workflow_time = self.calculate_workflows_time()

        # Base development time
        base_days = (
            code_time['days'] +
            markdown_time['days'] +
            workflow_time['days']
        )

        # Add planning overhead (30% additional time)
        planning_days = base_days * self.benchmarks.planning_overhead_factor
        total_days = base_days + planning_days

        # Convert to various time units
        total_hours = total_days * self.benchmarks.hours_per_day
        total_weeks = total_days / 5  # 5 working days per week
        total_months = total_weeks / 4  # ~4 weeks per month

        return {
            'code': code_time,
            'markdown': markdown_time,
            'workflows': workflow_time,
            'base_days': base_days,
            'planning_overhead_days': planning_days,
            'total_days': total_days,
            'total_hours': total_hours,
            'total_weeks': total_weeks,
            'total_months': total_months,
            'skills_count': len(self.stats['skills'])
        }

    def generate_report(self) -> str:
        """Generate formatted ROI report."""
        results = self.calculate_total()

        report = []
        report.append("=" * 70)
        report.append("ROI ANALYSIS: MANUAL DEVELOPMENT TIME ESTIMATE")
        report.append("=" * 70)
        report.append("")

        report.append("METHODOLOGY:")
        report.append("-------------")
        report.append("This analysis estimates the time required to manually develop")
        report.append("the claude-skills repository using industry productivity benchmarks.")
        report.append("")
        report.append("INDUSTRY BENCHMARKS USED:")
        report.append(f"  • Code: {self.benchmarks.code_loc_per_day} LOC/day")
        report.append("    (Source: US projects mean 26.4, median 17.6 LOC/day)")
        report.append(f"  • Technical Documentation: {self.benchmarks.doc_lines_per_day} lines/day")
        report.append("    (Source: 2 pages/day standard, ~50 lines per page)")
        report.append(f"  • Architecture/Planning: {self.benchmarks.architecture_lines_per_day} lines/day")
        report.append("    (More thought required than general docs)")
        report.append(f"  • Planning Overhead: +{int(self.benchmarks.planning_overhead_factor * 100)}%")
        report.append("    (Source: 30% of project time on planning/design)")
        report.append("")

        report.append("REPOSITORY COMPOSITION:")
        report.append("----------------------")
        report.append(f"  • Skills: {results['skills_count']}")
        report.append(f"  • Markdown Files: {self.stats['markdown']['files']} ({self.stats['markdown']['lines']:,} lines)")
        report.append(f"  • Code Files: {self.stats['code']['files']} ({self.stats['code']['lines']:,} lines)")
        report.append(f"  • Workflow Files: {self.stats['workflows']['files']} ({self.stats['workflows']['lines']:,} lines)")
        report.append("")

        report.append("TIME BREAKDOWN:")
        report.append("---------------")

        # Markdown breakdown
        report.append("Markdown (Architecture/Planning/Documentation):")
        md = results['markdown']
        report.append(f"  Total: {md['days']:.1f} days ({md['hours']:.1f} hours)")
        for category, data in md['breakdown'].items():
            if data['lines'] > 0:
                cat_name = category.replace('_', ' ').title()
                report.append(f"    • {cat_name}: {data['lines']:,} lines = {data['days']:.1f} days ({data['hours']:.1f} hours)")

        # Code breakdown
        report.append("")
        report.append("Code (Scripts/Automation):")
        code = results['code']
        report.append(f"  Total: {code['days']:.1f} days ({code['hours']:.1f} hours)")

        # Workflows breakdown
        if results['workflows']['lines'] > 0:
            report.append("")
            report.append("Workflows (CI/CD):")
            wf = results['workflows']
            report.append(f"  Total: {wf['days']:.1f} days ({wf['hours']:.1f} hours)")

        report.append("")
        report.append("TOTAL ESTIMATE:")
        report.append("===============")
        report.append(f"  Base Development Time: {results['base_days']:.1f} days")
        report.append(f"  Planning Overhead (+30%): {results['planning_overhead_days']:.1f} days")
        report.append("")
        report.append(f"  ► TOTAL DEVELOPMENT TIME: {results['total_days']:.1f} days")
        report.append(f"                            ({results['total_hours']:.1f} hours)")
        report.append(f"                            ({results['total_weeks']:.1f} weeks)")
        report.append(f"                            ({results['total_months']:.1f} months)")
        report.append("")

        # Cost estimates
        report.append("COST ESTIMATES (assuming standard rates):")
        report.append("------------------------------------------")

        # Different role rates (conservative US market estimates)
        senior_dev_rate = 150  # $/hour
        tech_writer_rate = 100  # $/hour
        architect_rate = 175  # $/hour

        # Estimate split: 50% architect/planning, 30% dev, 20% tech writing
        architect_hours = results['total_hours'] * 0.50
        dev_hours = results['total_hours'] * 0.30
        writer_hours = results['total_hours'] * 0.20

        architect_cost = architect_hours * architect_rate
        dev_cost = dev_hours * senior_dev_rate
        writer_cost = writer_hours * tech_writer_rate
        total_cost = architect_cost + dev_cost + writer_cost

        report.append(f"  • Solution Architect ({architect_hours:.0f}h @ ${architect_rate}/h): ${architect_cost:,.0f}")
        report.append(f"  • Senior Developer ({dev_hours:.0f}h @ ${senior_dev_rate}/h): ${dev_cost:,.0f}")
        report.append(f"  • Technical Writer ({writer_hours:.0f}h @ ${tech_writer_rate}/h): ${writer_cost:,.0f}")
        report.append("")
        report.append(f"  ► ESTIMATED TOTAL COST: ${total_cost:,.0f}")
        report.append("")

        report.append("KEY INSIGHTS:")
        report.append("-------------")
        avg_time_per_skill = results['total_days'] / results['skills_count']
        report.append(f"  • Average time per skill: {avg_time_per_skill:.1f} days")
        report.append(f"  • Markdown represents {(md['lines']/(self.stats['markdown']['lines']+self.stats['code']['lines']))*100:.0f}% of content")
        report.append(f"  • Architecture/planning is the major component ({md['breakdown']['skill_definitions']['days']:.1f} days)")
        report.append("")

        report.append("=" * 70)

        return "\n".join(report)

    def save_results(self, filename='roi_results.json'):
        """Save detailed results to JSON."""
        results = self.calculate_total()
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        return filename


def main():
    # Load repository statistics
    with open('repo_stats.json', 'r') as f:
        stats = json.load(f)

    # Initialize benchmarks and calculator
    benchmarks = ProductivityBenchmarks()
    calculator = ROICalculator(stats, benchmarks)

    # Generate and print report
    report = calculator.generate_report()
    print(report)

    # Save detailed results
    calculator.save_results()
    print(f"\nDetailed results saved to roi_results.json")

    # Save report to file
    with open('roi_report.txt', 'w') as f:
        f.write(report)
    print(f"Full report saved to roi_report.txt")


if __name__ == '__main__':
    main()
