# Comprehensive System Review Framework

## Initial Review Framework
```
IMPORTANT: This is a multi-phase review process that must be completed in order.
Each phase builds upon the previous and requires evidence-based documentation.

Phase 0: Setup [REQUIRED]
1. Review 03_review_template.md structure
2. Create initial report file using template structure using the format "runtime_review_report" + current datetime + ".md"
3. Ensure that all content produced is saved to the single file.
4. Read 02_review_instructions.md for analysis frameworks

Phase 0.5: Automated Analysis [REQUIRED]
1. Run functional_coverage_analyzer.py and document results
2. Run test_gap_analyzer.py and document results
3. Run test_quality_analyzer.py and document results
4. Document evidence in report according to automated analysis template
5. Create required action items based on findings

Phase 1: File Analysis [REQUIRED]
Follow the Component Analysis Framework from 02_review_instructions.md for each file:
1. All root directory files
2. All src/ directory files
3. All test files
4. All configuration files
5. Update report after EACH file analysis

Phase 2: System Analysis [ONLY AFTER FILE ANALYSIS]
Use analysis frameworks from 02_review_instructions.md sections:
- Component Interaction Analysis
- Data Flow Analysis
- Resource Management Analysis 
- Error Handling Analysis
- Security Analysis Framework

Phase 3: Evidence Collection [CONTINUOUS]
Document according to 02_review_instructions.md evidence requirements:
- Code Evidence (file:line citations)
- Runtime Evidence (logs, metrics)
- Test Evidence (test results, coverage)
```

## Review Process Requirements

### Evidence Documentation
For each claim or metric in the report:
```
[CLAIM/METRIC]: Specific observation or measurement
[EVIDENCE]: 
- Code: {file:line} references
- Runtime: Log entries or metrics
- Tests: Test results or coverage data
[VERIFICATION]: How this was validated
```

### Issue Documentation 
Use Root Cause Analysis Framework from 02_review_instructions.md:
```
[ISSUE-ID]: Descriptive title
[SYMPTOMS]: Observable issues
[EVIDENCE]: Specific examples/locations
[ROOT CAUSE]: Follow Five Whys technique
[IMPACT]: Business and technical impact
[RECOMMENDATIONS]: Evidence-based solutions
```

### Progress Tracking
- Update report after each file analysis
- Document all evidence immediately when found
- Link issues to specific code locations
- Show progressive understanding of system

### Validation Requirements
- All metrics must have citations
- All issues must have evidence
- All recommendations must be justified
- All claims must be verifiable

## Output Requirements

### Report Structure
- Must follow 03_review_template.md exactly
- Each section must have evidence
- Progressive updates as analysis continues
- Clear traceability of claims

### Evidence Quality
1. Code Evidence:
   - Exact file:line citations
   - Relevant code snippets
   - Context explanation

2. Runtime Evidence:
   - Log entries
   - Performance metrics
   - Error patterns
   - State transitions

3. Test Evidence:
   - Test results
   - Coverage data
   - Performance benchmarks
   - Error scenarios

### Documentation Standards
1. Clarity:
   - Clear separation of facts vs analysis
   - Evidence linked to conclusions
   - Traceable recommendations

2. Completeness:
   - All template sections filled
   - All claims supported
   - All issues documented
   - All recommendations justified

3. Usefulness:
   - Actionable findings
   - Clear priorities
   - Implementation guidance
   - Verification criteria

## Analysis Frameworks Reference

Reference the following frameworks from 02_review_instructions.md:
1. Component Analysis Framework
2. Root Cause Analysis Framework
3. Performance Analysis Framework
4. Security Analysis Framework
5. Configuration Analysis Framework
6. Testing Analysis Framework

## Documentation Flow

### 1. File Analysis Documentation
For each file analyzed:
```
[FILE]: path/to/file
[PURPOSE]: Clear description of responsibility
[ANALYSIS]: Using relevant frameworks from 02_review_instructions.md
[FINDINGS]: Evidence-based observations
[ISSUES]: Any identified problems with evidence
[METRICS]: Only verified/cited metrics
```

### 2. System Analysis Documentation
After completing all file analysis:
```
[COMPONENT]: Component name
[INTERACTIONS]: How it works with other components
[EVIDENCE]: Supporting file analysis findings
[PATTERNS]: Identified architectural patterns
[ISSUES]: Cross-component issues found
```

### 3. Issue Documentation
For each identified issue:
```
[ISSUE-ID]: Unique identifier
[CATEGORY]: Issue type from 02_review_instructions.md
[EVIDENCE]: Multiple sources supporting issue
[ANALYSIS]: Using relevant framework
[IMPACT]: Supported by evidence
[RECOMMENDATION]: Based on analysis
```

### 4. Recommendation Documentation
For each recommendation:
```
[REC-ID]: Unique identifier
[JUSTIFICATION]: Evidence from analysis
[AFFECTED_COMPONENTS]: From file analysis
[IMPLEMENTATION]: Specific changes needed
[VERIFICATION]: How to validate fix
```

## Required Outputs

1. Complete System Understanding:
   - Every component's purpose
   - All interactions documented
   - Clear evidence trail
   - No unsupported claims

2. Issue Analysis:
   - Root causes identified
   - Impact assessed
   - Solutions proposed
   - All with evidence

3. Recommendations:
   - Prioritized improvements
   - Implementation guidance
   - Resource requirements
   - Success criteria

4. Metrics and Evidence:
   - Performance data
   - Quality metrics
   - Security assessment
   - All with citations

## Completion Checklist

- [ ] Report structure matches template
- [ ] All files analyzed
- [ ] All claims have evidence
- [ ] All issues documented
- [ ] All recommendations justified
- [ ] Progressive updates shown
- [ ] No unsupported statements

## Rules of Operation [STRICT]

1. Start with file analysis
2. Document evidence immediately
3. Update report progressively
4. No claims without citations
5. No recommendations without justification
6. Follow all frameworks from 02_review_instructions.md
7. Use all templates as specified

## Report Initialization

### Initial Report Creation
1. Create report file using structure from 03_review_template.md
2. Add initial metadata section:
   ```
   # System Review Report
   Date: YYYY-MM-DD
   Reviewer: [Name]
   Version: 1.0
   Status: In Progress
   
   ## Review Progress
   - [ ] Project Structure Analysis
   - [ ] Source Code Analysis
   - [ ] Test Analysis
   - [ ] Configuration Analysis
   - [ ] System Analysis
   - [ ] Recommendations
   ```

### Progressive Updates
After each file analysis:
1. Update relevant template sections
2. Document evidence immediately
3. Link to framework used from 02_review_instructions.md
4. Show progress status update

Example progress update:
```
## Review Progress Update
[FILE]: src/validation/engine.py
[FRAMEWORK]: Component Analysis Framework (02_review_instructions.md#component-analysis)
[FINDINGS]: Evidence-based observations
[TEMPLATE_SECTIONS_UPDATED]: 
- Import Analysis
- Resource Management
[NEXT]: Proceeding to src/validation/rules.py
```

## Framework Integration Points

### Component Analysis Integration
Reference sections from 02_review_instructions.md:
1. Interface Analysis -> Component Assessment Checklist
2. Resource Management -> Resource Management Patterns
3. Error Handling -> Error Management Framework

### Root Cause Analysis Integration
Use techniques from 02_review_instructions.md:
1. Five Whys -> Root Cause Detection Process
2. Impact Analysis -> Impact Assessment Framework
3. Solution Design -> Implementation Planning Framework

### Performance Analysis Integration
Apply frameworks from 02_review_instructions.md:
1. Resource Utilization -> Performance Metrics Framework
2. Bottleneck Analysis -> Performance Analysis Patterns
3. Optimization -> Resource Optimization Framework

### Security Analysis Integration
Follow guidance from 02_review_instructions.md:
1. Threat Assessment -> Security Analysis Framework
2. Vulnerability Analysis -> Security Testing Framework
3. Controls Review -> Security Controls Framework